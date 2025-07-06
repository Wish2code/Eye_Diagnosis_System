# Eye Diagnosis System

A comprehensive web-based system for automated eye condition diagnosis using patient symptom data and ICD/CPT medical coding standards.

## Features

- **CSV File Upload**: Upload patient data in CSV format for batch processing
- **Advanced Symptom Matching**: Intelligent algorithm that matches patient symptoms to medical conditions
- **ICD/CPT Code Generation**: Automatically generates appropriate medical codes for diagnoses
- **Comprehensive Results**: Detailed diagnosis reports with prescriptions, severity levels, and treatment recommendations
- **Modern UI**: Beautiful, responsive web interface with real-time statistics
- **Data Export**: Download results in CSV format for further analysis
- **Error Handling**: Robust validation and error checking for data integrity

## System Requirements

- Python 3.7+
- Flask
- Required Python packages (see installation)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Eye_Diagnosis_System
```

2. Install required packages:
```bash
pip install flask werkzeug tabulate
```

3. Ensure the ICD/CPT codes database file is present:
   - `icd_cpt_codes_extended.csv` should be in the root directory

## Usage

1. **Start the application**:
```bash
python Diagnosis.py
```

2. **Access the web interface**:
   - Open your browser and go to `http://localhost:5000`

3. **Upload patient data**:
   - Prepare a CSV file with patient information (see CSV Format section)
   - Click "Upload CSV File" and select your file
   - The system will validate the file format and structure

4. **Process the data**:
   - Click "Process Data and Generate Results"
   - The system will analyze symptoms and generate diagnoses

5. **View results**:
   - View detailed results with statistics and charts
   - Download results as CSV for further analysis

## CSV File Format

The system expects a CSV file with the following columns (column names are flexible):

### Required Columns:
- **Email**: Patient email address
  - Acceptable column names: `email`, `patient_email`
- **Symptoms**: Patient symptoms
  - Acceptable column names: `symptoms`, `symptom`, `patient_symptoms`, `eye_symptoms`
  - Can be comma-separated in a single column or split across multiple columns: `symptom1`, `symptom2`, `symptom3`, etc.

### Optional Columns:
- **Affected Eye**: Which eye is affected
  - Acceptable column names: `affected_eye`, `eye`, `affected-eye`
  - Values: `left`, `right`, `both`
- **Onset Date**: When symptoms began
  - Acceptable column names: `onset_date`, `onset`, `date`
  - Format: YYYY-MM-DD

### Example CSV Format:
```csv
email,symptoms,affected_eye,onset_date
john.doe@email.com,"headache, Eye redness, irritation",left,2024-01-15
jane.smith@email.com,"Eye redness, sensation of a foreign object",right,2024-01-20
```

## Diagnosis Algorithm

The system uses an advanced symptom matching algorithm:

1. **Symptom Normalization**: Converts symptoms to lowercase and removes extra whitespace
2. **Jaccard Similarity**: Calculates similarity between patient symptoms and condition symptoms
3. **Threshold Matching**: Only returns diagnoses with similarity scores above 20%
4. **Best Match Selection**: Returns the condition with the highest similarity score

## Output Fields

The system generates the following information for each patient:

- **Patient Email**: Contact information
- **Diagnosis**: Identified eye condition
- **ICD Code**: International Classification of Diseases code
- **CPT Code**: Current Procedural Terminology code
- **Prescription**: Recommended treatment
- **Severity**: Condition severity level (10245=High, 10246=Medium, 10247=Low)
- **Diagnosis Status**: Active, Relapse, or Unknown
- **SOD**: Severity of Disease indicator
- **Insurance**: Insurance coverage information
- **Symptoms**: Original patient symptoms
- **Processed At**: Timestamp of processing

## File Structure

```
Eye_Diagnosis_System/
├── Diagnosis.py                 # Main Flask application
├── icd_cpt_codes_extended.csv   # ICD/CPT codes database
├── sample_patient_data.csv      # Example patient data
├── README.md                    # This file
├── templates/                   # HTML templates
│   ├── index.html              # Main dashboard
│   └── results.html            # Results display
└── uploads/                    # Uploaded files and results
    └── diagnosis_results.csv   # Generated results
```

## Error Handling

The system includes comprehensive error handling:

- **File Validation**: Checks file format and structure
- **Data Validation**: Ensures required fields are present
- **Symptom Processing**: Handles missing or malformed symptom data
- **Logging**: Detailed logs for debugging and monitoring

## Security Features

- **File Type Validation**: Only accepts CSV files
- **Secure Filename Handling**: Uses secure_filename for uploaded files
- **Input Sanitization**: Validates and cleans all input data
- **Error Messages**: User-friendly error messages without exposing system details

## Troubleshooting

### Common Issues:

1. **"No symptom columns found"**: Ensure your CSV contains at least one symptom-related column
2. **"Invalid file type"**: Make sure you're uploading a CSV file
3. **"No results found"**: Check that your CSV data is properly formatted and contains valid symptoms

### Logs:
- Check the console output for detailed error messages
- Logs are also written to help with debugging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support or questions, please open an issue in the repository.
