# Eye Diagnosis System

This project is a web-based application designed for processing medical data and generating diagnoses based on patients' symptoms. It uses Flask as the backend framework to handle file uploads, data processing, and rendering results.

## Features

- Upload patient vital data in JSON format.
- Process patient data and match symptoms with medical conditions using ICD/CPT codes.
- Generate a CSV file containing detailed diagnosis results.
- Display diagnosis results in a user-friendly web interface.

## Project Structure

```
.
├── diagnosis.py            # Main application logic
├── templates/
│   ├── index.html          # Main dashboard template
│   ├── results.html        # Template for displaying diagnosis results
├── uploads/                # Directory for storing uploaded files
├── icd_cpt_codes_extended.csv # Reference file containing ICD and CPT codes
└── README.md               # Documentation
```

## Requirements

- Python 3.7+
- Flask
- Bootstrap (for frontend styling)

Install the required Python dependencies:

```bash
pip install flask werkzeug
```

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/medical-data-diagnosis.git
cd medical-data-diagnosis
```

### 2. Set Up Environment

Ensure a directory named `uploads/` exists in the project root. This directory will store uploaded files.

Set a secret key for Flask in the `diagnosis.py` file:

```python
app.secret_key = 'your_secret_key_here'
```

### 3. Run the Application

Start the Flask development server:

```bash
python diagnosis.py
```

The application will be accessible at `http://127.0.0.1:5000/`.

## Usage

1. **Upload Data**: 
   - Navigate to the dashboard.
   - Upload a JSON file containing patient vital data.

2. **Process Data**:
   - Click the "Process Data and Generate Results" button to analyze the data.

3. **View Results**:
   - After processing, navigate to the "Results" page to view the diagnosis in a tabular format.

## Input File Formats

### Patient Vitals Data (JSON)

The JSON file should include patient details and symptoms:

```json
[
  {
    "personal_info": {
      "email": ["example@domain.com"]
    },
    "health_data": {
      "symptoms": ["blurred vision", "headache"],
      "affected-eye": ["left"],
      "onset": "2025-01-01"
    }
  }
]
```

### ICD/CPT Codes (CSV)

The CSV file `icd_cpt_codes_extended.csv` must have the following fields:

- `icd_code`, `cpt_code`, `condition`, `symptom1`, `symptom2`, `symptom3`, `prescription`, `severity`, `SOD`, `diagnosis_status`, `Insurance`

## Output

The results are saved as a CSV file named `diagnosis_results.csv` in the `uploads/` folder. It contains the following fields:

- Patient Email
- Diagnosis
- ICD Code
- Prescription
- CPT Code
- Affected Eye
- Onset Date
- Diagnosis Status
- Severity
- Insurance

## Troubleshooting

- Ensure the `icd_cpt_codes_extended.csv` file is present in the root directory.
- Verify that uploaded files follow the specified format.
- Check for missing or invalid data in input files.

---

Feel free to contribute or report issues to improve this application!
