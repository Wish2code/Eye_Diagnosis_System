# Diagnosis.py
from flask import Flask, render_template, request, flash, redirect, url_for, send_file, jsonify
import os
from werkzeug.utils import secure_filename
import csv
import json
import threading
from tabulate import tabulate
import logging
from datetime import datetime
import re

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

# ── AI chatbot model (lazy-loaded on first request) ──────────────────────────
_ai_model = None
_ai_tokenizer = None
_ai_model_lock = threading.Lock()


def _load_ai_model():
    """Lazily load and cache the Flan-T5-Small model. Thread-safe."""
    global _ai_model, _ai_tokenizer
    if _ai_model is not None:
        return True, None
    try:
        from transformers import T5ForConditionalGeneration, AutoTokenizer
        model_name = 'google/flan-t5-small'
        logger.info("Loading AI model: %s (first request only)", model_name)
        _ai_tokenizer = AutoTokenizer.from_pretrained(model_name)
        _ai_model = T5ForConditionalGeneration.from_pretrained(model_name)
        _ai_model.eval()
        logger.info("AI model loaded successfully")
        return True, None
    except ImportError as exc:
        msg = (
            f"Required packages missing: {exc}. "
            "Install with: pip install transformers torch sentencepiece"
        )
        logger.error(msg)
        return False, msg
    except Exception as exc:
        logger.error("Failed to load AI model: %s", exc)
        return False, str(exc)


def _build_results_context(results):
    """Build a concise text context from diagnosis results for the AI prompt."""
    if not results:
        return ""
    total = len(results)
    diagnoses = {}
    severities = {}
    prescriptions = set()
    sev_labels = {'10245': 'High', '10246': 'Medium', '10247': 'Low'}

    for r in results:
        diag = r.get('diagnosis', 'Unknown')
        sev = r.get('Severity', r.get('severity', 'Unknown'))
        pres = r.get('prescription', '')
        diagnoses[diag] = diagnoses.get(diag, 0) + 1
        severities[sev] = severities.get(sev, 0) + 1
        if pres and pres not in ('Unknown', ''):
            prescriptions.add(pres)

    diag_text = '; '.join(
        f"{k} ({v} patient{'s' if v > 1 else ''})" for k, v in diagnoses.items()
    )
    sev_text = '; '.join(
        f"{sev_labels.get(k, k)}: {v}" for k, v in severities.items()
    )
    pres_text = '; '.join(list(prescriptions)[:5]) if prescriptions else 'None'

    return (
        f"Total patients analyzed: {total}. "
        f"Diagnoses: {diag_text}. "
        f"Severity distribution: {sev_text}. "
        f"Prescriptions given: {pres_text}."
    )


def _severity_label(code):
    severity_labels = {
        '10245': 'High',
        '10246': 'Medium',
        '10247': 'Low'
    }
    return severity_labels.get(str(code), str(code) if code else 'Unknown')


def _compute_results_analytics(results):
    """Compute structured analytics from diagnosis results for robust chatbot responses."""
    analytics = {
        'total_patients': len(results),
        'diagnosis_counts': {},
        'severity_counts': {},
        'eye_counts': {},
        'status_counts': {},
        'insurance_counts': {},
        'prescription_counts': {},
        'unknown_diagnoses': 0,
        'unknown_prescriptions': 0,
    }

    for row in results:
        diagnosis = row.get('diagnosis', 'Unknown').strip() or 'Unknown'
        severity = row.get('Severity', 'Unknown').strip() or 'Unknown'
        eye = row.get('Eye', 'Unknown').strip() or 'Unknown'
        status = row.get('Diagnosis_status', 'Unknown').strip() or 'Unknown'
        insurance = row.get('Insurance', 'Unknown').strip() or 'Unknown'
        prescription = row.get('prescription', 'Unknown').strip() or 'Unknown'

        analytics['diagnosis_counts'][diagnosis] = analytics['diagnosis_counts'].get(diagnosis, 0) + 1
        analytics['severity_counts'][severity] = analytics['severity_counts'].get(severity, 0) + 1
        analytics['eye_counts'][eye] = analytics['eye_counts'].get(eye, 0) + 1
        analytics['status_counts'][status] = analytics['status_counts'].get(status, 0) + 1
        analytics['insurance_counts'][insurance] = analytics['insurance_counts'].get(insurance, 0) + 1
        analytics['prescription_counts'][prescription] = analytics['prescription_counts'].get(prescription, 0) + 1

        if diagnosis.lower() == 'unknown':
            analytics['unknown_diagnoses'] += 1
        if prescription.lower() == 'unknown':
            analytics['unknown_prescriptions'] += 1

    sorted_diagnoses = sorted(
        analytics['diagnosis_counts'].items(), key=lambda item: item[1], reverse=True
    )
    analytics['top_diagnoses'] = sorted_diagnoses[:3]

    return analytics


def _format_analytics_for_prompt(analytics):
    total = analytics['total_patients']
    if total == 0:
        return "No diagnosis records are available."

    def _fmt_distribution(distribution, mapper=None):
        if not distribution:
            return "None"
        parts = []
        for key, count in sorted(distribution.items(), key=lambda item: item[1], reverse=True):
            label = mapper(key) if mapper else key
            share = (count / total) * 100 if total else 0
            parts.append(f"{label}: {count} ({share:.1f}%)")
        return "; ".join(parts)

    return (
        f"Total patients: {total}. "
        f"Top diagnoses: {_fmt_distribution(dict(analytics['top_diagnoses']))}. "
        f"All diagnoses: {_fmt_distribution(analytics['diagnosis_counts'])}. "
        f"Severity distribution: {_fmt_distribution(analytics['severity_counts'], _severity_label)}. "
        f"Affected eye distribution: {_fmt_distribution(analytics['eye_counts'])}. "
        f"Diagnosis status distribution: {_fmt_distribution(analytics['status_counts'])}. "
        f"Prescription distribution: {_fmt_distribution(analytics['prescription_counts'])}. "
        f"Unknown diagnoses: {analytics['unknown_diagnoses']}."
    )


def _build_structured_summary(analytics):
    """Create a deterministic and informative summary used as fallback and baseline."""
    total = analytics['total_patients']
    if total == 0:
        return "No diagnosis results are available yet. Run a diagnosis to generate a clinical summary."

    high = analytics['severity_counts'].get('10245', 0)
    medium = analytics['severity_counts'].get('10246', 0)
    low = analytics['severity_counts'].get('10247', 0)
    elevated = high + medium

    top_lines = []
    for diagnosis, count in analytics['top_diagnoses']:
        share = (count / total) * 100
        top_lines.append(f"{diagnosis} ({count}, {share:.1f}%)")
    top_text = ", ".join(top_lines) if top_lines else "No dominant diagnosis pattern detected"

    eye_parts = []
    for eye, count in sorted(analytics['eye_counts'].items(), key=lambda item: item[1], reverse=True):
        eye_parts.append(f"{eye}: {count}")
    eye_text = ", ".join(eye_parts) if eye_parts else "Not available"

    status_parts = []
    for status, count in sorted(analytics['status_counts'].items(), key=lambda item: item[1], reverse=True):
        status_parts.append(f"{status}: {count}")
    status_text = ", ".join(status_parts) if status_parts else "Not available"

    recommendation = (
        "Prioritize follow-up for high-severity cases, confirm uncertain diagnoses, "
        "and review treatment consistency across similar symptom clusters."
    )

    return (
        "Clinical Results Summary\n"
        f"- Cohort size: {total} patients were analyzed.\n"
        f"- Key diagnostic findings: {top_text}.\n"
        f"- Risk profile: High severity {high}, Medium severity {medium}, Low severity {low} "
        f"(elevated risk total: {elevated}).\n"
        f"- Affected-eye pattern: {eye_text}.\n"
        f"- Diagnosis status mix: {status_text}.\n"
        f"- Data quality signal: {analytics['unknown_diagnoses']} records remain classified as Unknown diagnosis.\n"
        f"- Recommended next step: {recommendation}"
    )


def _is_summary_request(message):
    text = message.lower()
    return any(keyword in text for keyword in (
        'summary', 'summarize', 'summarise', 'overview', 'report', 'key findings', 'insights'
    ))


def _answer_general_app_question(message):
    """Provide deterministic, context-aware answers for landing-page chatbot usage."""
    text = message.lower().strip()

    if any(word in text for word in ('hello', 'hi', 'hey', 'what can you do', 'help')):
        return (
            "I can help you use the Eye Diagnosis System. "
            "You can upload a patient CSV, run diagnosis, view ICD/CPT-coded results, and download the output. "
            "After diagnosis is complete, I can generate a detailed clinical-style summary and answer result-specific questions."
        )

    if any(word in text for word in ('csv', 'format', 'columns', 'upload')):
        return (
            "The upload file must be a CSV. Include patient email and at least one symptom field. "
            "Supported symptom columns include symptoms, symptom, patient_symptoms, eye_symptoms, or split fields like symptom1/symptom2. "
            "Optional fields include affected_eye and onset_date."
        )

    if any(word in text for word in ('how', 'workflow', 'steps', 'process', 'run diagnosis')):
        return (
            "Workflow: 1) Upload a CSV file (or load the sample file). "
            "2) Click Run Diagnosis to match symptoms with ICD/CPT mappings. "
            "3) Open the Results page to review distributions, detailed rows, and download the results CSV."
        )

    if any(word in text for word in ('summary', 'insight', 'insights', 'ai summary')):
        return (
            "AI summaries are generated only after diagnosis results exist. "
            "Run diagnosis first, then open the Results page and click Generate AI Summary for a structured clinical analysis."
        )

    if any(word in text for word in ('model', 'ai model', 'flan', 'local', 'api key')):
        return (
            "The chatbot uses the local google/flan-t5-small model through Hugging Face Transformers. "
            "No API key is required, and after the first download/load, responses run locally."
        )

    return (
        "I can answer questions about app usage, expected CSV structure, and diagnosis workflow. "
        "For patient-level insights and clinical summaries, run diagnosis and ask from the Results page."
    )


def _answer_analytics_question(message, analytics):
    """Return direct, reliable answers for common result questions before using model generation."""
    text = message.lower()
    total = analytics['total_patients']

    if re.search(r'\b(total|how many patients|patient count)\b', text):
        return f"A total of {total} patients were analyzed in the current diagnosis run."

    if re.search(r'\b(high severity|high-risk|critical)\b', text):
        high = analytics['severity_counts'].get('10245', 0)
        share = (high / total) * 100 if total else 0
        return f"High-severity cases: {high} of {total} patients ({share:.1f}%)."

    if re.search(r'\b(medium severity)\b', text):
        medium = analytics['severity_counts'].get('10246', 0)
        share = (medium / total) * 100 if total else 0
        return f"Medium-severity cases: {medium} of {total} patients ({share:.1f}%)."

    if re.search(r'\b(low severity)\b', text):
        low = analytics['severity_counts'].get('10247', 0)
        share = (low / total) * 100 if total else 0
        return f"Low-severity cases: {low} of {total} patients ({share:.1f}%)."

    if re.search(r'\b(most common|top diagnosis|most frequent)\b', text):
        if analytics['top_diagnoses']:
            diagnosis, count = analytics['top_diagnoses'][0]
            share = (count / total) * 100 if total else 0
            return f"The most common diagnosis is {diagnosis} with {count} patients ({share:.1f}%)."
        return "No diagnosis distribution is available yet."

    if re.search(r'\b(unknown|uncertain)\b', text):
        unknown = analytics['unknown_diagnoses']
        share = (unknown / total) * 100 if total else 0
        return f"Unknown diagnoses: {unknown} of {total} patients ({share:.1f}%)."

    return None


def _response_is_too_generic(response_text, total_patients):
    if not response_text:
        return True

    generic_markers = [
        'common eye disease',
        'in summary',
        'eye disease is a',
    ]
    text = response_text.lower()
    if any(marker in text for marker in generic_markers):
        return True

    # For non-trivial datasets, good summaries should contain at least one numeric detail.
    if total_patients > 1 and not re.search(r'\d', response_text):
        return True

    return False


def _generate_ai_response(prompt):
    """Generate a response from the local Flan-T5-Small model."""
    with _ai_model_lock:
        success, error = _load_ai_model()
        if not success:
            return None, error

    try:
        import torch
        inputs = _ai_tokenizer(
            prompt, return_tensors='pt', max_length=512, truncation=True
        )
        with torch.no_grad():
            outputs = _ai_model.generate(
                **inputs,
                max_new_tokens=200,
                num_beams=4,
                no_repeat_ngram_size=3,
                early_stopping=True,
            )
        response = _ai_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response.strip(), None
    except Exception as exc:
        logger.error("AI generation error: %s", exc)
        return None, str(exc)

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

@app.route('/use_sample', methods=['POST'])
def use_sample():
    """Copy the built-in sample CSV to uploads so users can test without their own file."""
    import shutil
    sample_file = 'sample_patient_data.csv'
    dest_file = os.path.join(app.config['UPLOAD_FOLDER'], 'patient_data.csv')
    try:
        shutil.copy(sample_file, dest_file)
        data = read_csv(dest_file)
        flash(f'Sample data loaded successfully with {len(data)} patient records. Click "Run Diagnosis" to continue.', 'success')
    except FileNotFoundError:
        flash('Sample data file not found on the server.', 'error')
    except Exception as e:
        logger.error(f"Error loading sample data: {e}")
        flash(f'Error loading sample data: {str(e)}', 'error')
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


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chatbot messages and return AI-generated responses as JSON."""
    data = request.get_json(silent=True)
    if not data or not data.get('message', '').strip():
        return jsonify({'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    page_context = data.get('context', 'results').strip().lower()

    # Landing page chatbot: answer general application questions without requiring diagnosis results.
    if page_context == 'landing':
        return jsonify({'response': _answer_general_app_question(user_message)})

    # Load the most recent diagnosis results
    results_file = os.path.join(app.config['UPLOAD_FOLDER'], "diagnosis_results.csv")
    try:
        with open(results_file, mode='r', encoding='utf-8') as f:
            results = list(csv.DictReader(f))
    except FileNotFoundError:
        if _is_summary_request(user_message):
            return jsonify({
                'response': 'No diagnosis results found yet. Run a diagnosis first, then request an AI summary on the Results page.'
            })
        return jsonify({'response': _answer_general_app_question(user_message)})

    if not results:
        if _is_summary_request(user_message):
            return jsonify({
                'response': 'No diagnosis results available. Please process patient data first, then generate the summary.'
            })
        return jsonify({'response': _answer_general_app_question(user_message)})

    analytics = _compute_results_analytics(results)
    detailed_context = _format_analytics_for_prompt(analytics)
    deterministic_summary = _build_structured_summary(analytics)

    # Return direct metric answers for common queries to avoid vague model replies.
    direct_answer = _answer_analytics_question(user_message, analytics)
    if direct_answer:
        return jsonify({'response': direct_answer})

    if _is_summary_request(user_message):
        prompt = (
            "You are a clinical data analyst assistant. "
            "Create a clear, professional summary with concrete numbers and practical interpretation. "
            "Do not use generic filler. Keep all facts consistent with the data. "
            "Include sections: Key Findings, Risk Priorities, and Recommended Actions. "
            f"Dataset facts: {detailed_context} "
            f"Baseline summary to preserve facts: {deterministic_summary} "
            "Final summary:"
        )
    else:
        if any(token in user_message.lower() for token in ('workflow', 'upload', 'csv', 'how to', 'steps', 'model')):
            return jsonify({'response': _answer_general_app_question(user_message)})

        prompt = (
            "You are a professional medical assistant for an eye diagnosis dashboard. "
            "Answer the user question using the dataset facts with concrete numbers and concise interpretation. "
            "If the question is ambiguous, answer with the best available data and suggest one precise follow-up question. "
            f"Dataset facts: {detailed_context} "
            f"Question: {user_message} "
            "Answer:"
        )

    response, error = _generate_ai_response(prompt)
    if error:
        logger.error("AI model error in /chat: %s", error)
        # Preserve functionality even when local model is unavailable.
        if _is_summary_request(user_message):
            return jsonify({'response': deterministic_summary})
        return jsonify({
            'response': (
                "The AI model is currently unavailable, so here is a reliable data-based overview: "
                f"{deterministic_summary}"
            )
        })

    if _response_is_too_generic(response, analytics['total_patients']):
        if _is_summary_request(user_message):
            response = deterministic_summary
        else:
            response = (
                "The request was interpreted with the available dataset. "
                f"{deterministic_summary} "
                "You can ask a focused follow-up like: 'How many high-severity patients are there?'"
            )

    return jsonify({'response': response})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info("Starting Eye Diagnosis System...")
    app.run(host='0.0.0.0', port=port, debug=False)
