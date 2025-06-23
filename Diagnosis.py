# app.py
from flask import Flask, render_template, request, flash, redirect, url_for, send_file
import os
from werkzeug.utils import secure_filename
import csv
import json
from tabulate import tabulate
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}  # Changed to only allow CSV files
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    if not filename:
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_csv(file_name):
    """Reads a CSV file and returns a list of dictionaries."""
    try:
        with open(file_name, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            data = list(reader)
            logger.info(f"Successfully loaded {len(data)} records from {file_name}")
            return data
    except FileNotFoundError:
        logger.error(f"Error: The file '{file_name}' was not found.")
        return []
    except Exception as e:
        logger.error(f"An error occurred while reading '{file_name}': {e}")
        return []

def write_csv(file_name, fieldnames, data):
    """Writes a list of dictionaries to a CSV file."""
    try:
        with open(file_name, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        logger.info(f"Successfully wrote {len(data)} records to {file_name}")
        return True
    except Exception as e:
        logger.error(f"An error occurred while writing to '{file_name}': {e}")
        return False

def extract_symptoms_from_csv_row(row):
    """Extract symptoms from a CSV row. Handles various possible column names."""
    symptoms = []
    
    # Common symptom column names
    symptom_columns = [
        'symptoms', 'symptom', 'patient_symptoms', 'eye_symptoms',
        'symptom1', 'symptom2', 'symptom3', 'symptom4', 'symptom5',
        'primary_symptom', 'secondary_symptom', 'tertiary_symptom'
    ]
    
    for col in symptom_columns:
        if col in row and row[col]:
            # Handle both single symptoms and comma-separated lists
            symptom_value = str(row[col]).strip()
            if ',' in symptom_value:
                # Split by comma and clean each symptom
                symptom_list = [s.strip() for s in symptom_value.split(',') if s.strip()]
                symptoms.extend(symptom_list)
            else:
                symptoms.append(symptom_value)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_symptoms = []
    for symptom in symptoms:
        if symptom.lower() not in seen:
            seen.add(symptom.lower())
            unique_symptoms.append(symptom)
    
    return unique_symptoms

def normalize_symptoms(symptoms):
    """Normalize symptoms for better matching."""
    normalized = []
    for symptom in symptoms:
        if symptom:
            # Convert to lowercase and remove extra whitespace
            clean_symptom = symptom.lower().strip()
            normalized.append(clean_symptom)
    return normalized

def calculate_symptom_match_score(patient_symptoms, condition_symptoms):
    """Calculate a match score between patient symptoms and condition symptoms."""
    patient_normalized = normalize_symptoms(patient_symptoms)
    condition_normalized = normalize_symptoms(condition_symptoms)
    
    if not patient_normalized or not condition_normalized:
        return 0.0
    
    # Calculate intersection
    intersection = set(patient_normalized) & set(condition_normalized)
    
    # Calculate Jaccard similarity
    union = set(patient_normalized) | set(condition_normalized)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)

def diagnose_patient(symptoms, icd_data):
    """Finds the best-matching ICD code for the given symptoms using improved algorithm."""
    best_match = None
    best_score = 0.0
    
    for row in icd_data:
        condition_symptoms = [
            row.get("symptom1", "").strip(),
            row.get("symptom2", "").strip(),
            row.get("symptom3", "").strip()
        ]
        
        # Remove empty symptoms
        condition_symptoms = [s for s in condition_symptoms if s]
        
        if not condition_symptoms:
            continue
        
        # Calculate match score
        score = calculate_symptom_match_score(symptoms, condition_symptoms)
        
        if score > best_score:
            best_score = score
            best_match = row
    
    # Return best match if score is above threshold, otherwise return unknown
    if best_match and best_score >= 0.2:  # 20% similarity threshold
        return (
            best_match.get("condition", "Unknown"),
            best_match.get("icd_code", "DNE"),
            best_match.get("prescription", "Unknown"),
            best_match.get("severity", "Unknown"),
            best_match.get("SOD", "Unknown"),
            best_match.get("diagnosis_status", "Unknown"),
            best_match.get("Insurance", "Unknown")
        )
    
    return "Unknown", "DNE", "Unknown", "Unknown", "Unknown", "Unknown", "Unknown"

def validate_csv_structure(data):
    """Validate that the CSV contains required fields for diagnosis."""
    if not data:
        return False, "No data found in CSV file"
    
    # Check for at least one symptom-related column
    first_row = data[0]
    symptom_columns = [
        'symptoms', 'symptom', 'patient_symptoms', 'eye_symptoms',
        'symptom1', 'symptom2', 'symptom3', 'symptom4', 'symptom5',
        'primary_symptom', 'secondary_symptom', 'tertiary_symptom'
    ]
    
    has_symptoms = any(col in first_row for col in symptom_columns)
    if not has_symptoms:
        return False, "No symptom columns found in CSV file"
    
    return True, "CSV structure is valid"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    file_type = request.form.get('file_type')
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))
    
    # Fix the linter error by checking if filename exists
    if not file.filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if file_type == 'vitals':
            filename = 'patient_data.csv'  # Changed from JSON to CSV
        elif file_type == 'scheduling':
            filename = 'scheduling.csv'
        elif file_type == 'insurance':
            filename = 'insurance.csv'
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Validate the uploaded CSV file
        data = read_csv(file_path)
        is_valid, message = validate_csv_structure(data)
        
        if not is_valid:
            os.remove(file_path)  # Remove invalid file
            flash(f'Invalid CSV file: {message}', 'error')
            return redirect(url_for('index'))
        
        logger.info(f"Successfully uploaded {filename} with {len(data)} records")
        flash(f'Successfully uploaded {filename} with {len(data)} patient records', 'success')
        return redirect(url_for('index'))
    
    flash('Invalid file type. Please upload a CSV file.', 'error')
    return redirect(url_for('index'))

@app.route('/process', methods=['POST'])
def process_data():
    try:
        # Update file paths
        patient_data_file = os.path.join(app.config['UPLOAD_FOLDER'], "patient_data.csv")
        icd_cpt_file = "icd_cpt_codes_extended.csv"
        results_file = os.path.join(app.config['UPLOAD_FOLDER'], "diagnosis_results.csv")

        # Load patient data from CSV
        patient_data = read_csv(patient_data_file)
        if not patient_data:
            flash("Error: Patient data file is missing or empty. Please upload a CSV file first.", 'error')
            return redirect(url_for('index'))

        # Load ICD data
        icd_cpt_data = read_csv(icd_cpt_file)
        if not icd_cpt_data:
            flash("Error: ICD/CPT codes file is missing or empty. Please ensure icd_cpt_codes_extended.csv is in the root directory.", 'error')
            return redirect(url_for('index'))

        # Prepare diagnosis results
        results = []
        processed_count = 0
        error_count = 0
        
        for patient in patient_data:
            try:
                # Extract symptoms from CSV row
                symptoms = extract_symptoms_from_csv_row(patient)
                
                if not symptoms:
                    logger.warning(f"No symptoms found for patient row")
                    error_count += 1
                    continue
                
                # Extract other relevant fields
                patient_email = patient.get('email', patient.get('patient_email', 'unknown@email.com'))
                affected_eye = patient.get('affected_eye', patient.get('eye', patient.get('affected-eye', 'Unknown')))
                onset_date = patient.get('onset_date', patient.get('onset', patient.get('date', 'Unknown')))
                
                # Make diagnosis
                diagnosis, icd_code, prescription, severity, SOD, diagnosis_status, insurance = diagnose_patient(symptoms, icd_cpt_data)
                cpt_code = next((row["cpt_code"] for row in icd_cpt_data if row.get("icd_code") == icd_code), "DNE")

                results.append({
                    "patient_email": patient_email,
                    "diagnosis": diagnosis,
                    "icd_code": icd_code,
                    "prescription": prescription,
                    "cpt_code": cpt_code,
                    "Eye": affected_eye,
                    "Onset_date": onset_date,
                    "Insurance": insurance,
                    "Diagnosis_status": diagnosis_status,
                    "SOD": SOD,
                    "Severity": severity,
                    "Symptoms": ', '.join(symptoms),
                    "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing patient: {e}")
                error_count += 1
                continue

        # Write results
        fieldnames = [
            "patient_email", "diagnosis", "icd_code", "prescription", "cpt_code",
            "Eye", "Onset_date", "Diagnosis_status", "SOD", "Severity", "Insurance", "Symptoms", "processed_at"
        ]
        
        if write_csv(results_file, fieldnames, results):
            flash(f"Diagnosis complete! Processed {processed_count} patients successfully. {error_count} errors encountered.", 'success')
        else:
            flash("Error saving results to file.", 'error')
            
        return redirect(url_for('view_results'))

    except Exception as e:
        logger.error(f"Error during data processing: {e}")
        flash(f"An error occurred during processing: {str(e)}", 'error')
        return redirect(url_for('index'))

@app.route('/results')
def view_results():
    results_file = os.path.join(app.config['UPLOAD_FOLDER'], "diagnosis_results.csv")
    try:
        with open(results_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            results = list(reader)
            if not results:
                flash("No results found. Please process some data first.", 'info')
                return redirect(url_for('index'))
            
            # Calculate statistics
            total_patients = len(results)
            diagnoses = {}
            severity_counts = {}
            
            for result in results:
                diagnosis = result.get('diagnosis', 'Unknown')
                severity = result.get('Severity', 'Unknown')
                
                diagnoses[diagnosis] = diagnoses.get(diagnosis, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            return render_template('results.html', 
                                 results=results, 
                                 total_patients=total_patients,
                                 diagnoses=diagnoses,
                                 severity_counts=severity_counts)
                                 
    except FileNotFoundError:
        flash("No results file found. Please process the data first.", 'info')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error reading results: {e}")
        flash(f"An error occurred while reading results: {str(e)}", 'error')
        return redirect(url_for('index'))

@app.route('/download_results')
def download_results():
    """Download results as CSV file."""
    results_file = os.path.join(app.config['UPLOAD_FOLDER'], "diagnosis_results.csv")
    try:
        return send_file(results_file, as_attachment=True, download_name=f"diagnosis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    except FileNotFoundError:
        flash("No results file found.", 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    logger.info("Starting Eye Diagnosis System...")
    app.run(debug=True)
