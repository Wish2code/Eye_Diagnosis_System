# app.py
from flask import Flask, render_template, request, flash, redirect, url_for, send_file
import os
from werkzeug.utils import secure_filename
import csv
import json
from tabulate import tabulate

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'json', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_json(file_name):
    """Reads a JSON file and returns the parsed data."""
    try:
        with open(file_name, mode='r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{file_name}' was not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse JSON from '{file_name}': {e}")
        return []
    except Exception as e:
        print(f"An error occurred while reading '{file_name}': {e}")
        return []

def read_csv(file_name):
    """Reads a CSV file and returns a list of dictionaries."""
    try:
        with open(file_name, mode='r') as file:
            reader = csv.DictReader(file)
            return list(reader)
    except FileNotFoundError:
        print(f"Error: The file '{file_name}' was not found.")
        return []
    except Exception as e:
        print(f"An error occurred while reading '{file_name}': {e}")
        return []

def write_csv(file_name, fieldnames, data):
    """Writes a list of dictionaries to a CSV file."""
    try:
        with open(file_name, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"An error occurred while writing to '{file_name}': {e}")

def diagnose_patient(symptoms, icd_data):
    """Finds the best-matching ICD code for the given symptoms."""
    for row in icd_data:
        condition_symptoms = {row["symptom1"].strip(), row["symptom2"].strip(), row["symptom3"].strip()}
        if len(set(symptoms) & condition_symptoms) > 1:  # Check for symptom overlap
            return (
                row["condition"],
                row["icd_code"],
                row["prescription"],
                row["severity"],
                row["SOD"],
                row["diagnosis_status"],
                row.get("Insurance", "Unknown")
            )
    return "Unknown", "DNE", "Unknown", "Unknown", "Unknown", "Unknown", "Unknown"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    file_type = request.form.get('file_type')
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if file_type == 'vitals':
            filename = 'Vitals_team.json'
        elif file_type == 'scheduling':
            filename = 'scheduling.json'
        elif file_type == 'insurance':
            filename = 'insurance.json'
        
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f'Successfully uploaded {filename}')
        return redirect(url_for('index'))
    
    flash('Invalid file type')
    return redirect(request.url)

@app.route('/process', methods=['POST'])
def process_data():
    try:
        # Update file paths
        vitals_file = os.path.join(app.config['UPLOAD_FOLDER'], "Vitals_team.json")
        icd_cpt_file = "icd_cpt_codes_extended.csv"
        results_file = os.path.join(app.config['UPLOAD_FOLDER'], "diagnosis_results.csv")

        # Load vital data
        vitals_data = read_json(vitals_file)
        if not vitals_data:
            flash("Error: Vitals data file is missing or empty. Please upload Vitals_team.json first.")
            return redirect(url_for('index'))

        # Load ICD data
        icd_cpt_data = read_csv(icd_cpt_file)
        if not icd_cpt_data:
            flash("Error: ICD/CPT codes file is missing or empty. Please ensure icd_cpt_codes_extended.csv is in the root directory.")
            return redirect(url_for('index'))

        # Prepare diagnosis results
        results = []
        for patient in vitals_data:
            patient_info = patient["personal_info"]
            health_data = patient["health_data"]
            symptoms = health_data["symptoms"]
            patient_email = patient_info["email"][0]

            diagnosis, icd_code, prescription, severity, SOD, diagnosis_status, insurance = diagnose_patient(symptoms, icd_cpt_data)
            cpt_code = next((row["cpt_code"] for row in icd_cpt_data if row["icd_code"] == icd_code), "DNE")

            results.append({
                "patient_email": patient_email,
                "diagnosis": diagnosis,
                "icd_code": icd_code,
                "prescription": prescription,
                "cpt_code": cpt_code,
                "Eye": health_data["affected-eye"][0],
                "Onset_date": health_data["onset"],
                "Insurance": insurance,
                "Diagnosis_status": diagnosis_status,
                "SOD": SOD,
                "Severity": severity
            })

        # Write results
        fieldnames = [
            "patient_email", "diagnosis", "icd_code", "prescription", "cpt_code",
            "Eye", "Onset_date", "Diagnosis_status", "SOD", "Severity", "Insurance"
        ]
        write_csv(results_file, fieldnames, results)
        flash("Diagnosis complete! Results saved successfully.")
        return redirect(url_for('view_results'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return redirect(url_for('index'))

@app.route('/results')
def view_results():
    results_file = os.path.join(app.config['UPLOAD_FOLDER'], "diagnosis_results.csv")
    try:
        with open(results_file, mode='r') as file:
            reader = csv.DictReader(file)
            results = list(reader)
            if not results:
                flash("No results found. Please process some data first.")
                return redirect(url_for('index'))
            return render_template('results.html', results=results)
    except FileNotFoundError:
        flash("No results file found. Please process the data first.")
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"An error occurred while reading results: {str(e)}")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
