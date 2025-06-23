#!/usr/bin/env python3
"""
Test script for the Eye Diagnosis System
This script demonstrates the improved functionality of the CSV-based diagnosis system.
"""

import csv
import os
from Diagnosis import read_csv, extract_symptoms_from_csv_row, diagnose_patient, validate_csv_structure

def test_csv_reading():
    """Test reading the sample CSV file."""
    print("=== Testing CSV Reading ===")
    try:
        data = read_csv('sample_patient_data.csv')
        print(f"✓ Successfully read {len(data)} records from sample CSV")
        print(f"✓ First record keys: {list(data[0].keys())}")
        return data
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return None

def test_symptom_extraction():
    """Test symptom extraction from CSV rows."""
    print("\n=== Testing Symptom Extraction ===")
    data = read_csv('sample_patient_data.csv')
    if not data:
        return
    
    for i, row in enumerate(data[:3]):  # Test first 3 records
        symptoms = extract_symptoms_from_csv_row(row)
        print(f"Patient {i+1}: {symptoms}")
        print(f"✓ Extracted {len(symptoms)} symptoms")

def test_csv_validation():
    """Test CSV structure validation."""
    print("\n=== Testing CSV Validation ===")
    data = read_csv('sample_patient_data.csv')
    if not data:
        return
    
    is_valid, message = validate_csv_structure(data)
    if is_valid:
        print(f"✓ {message}")
    else:
        print(f"✗ {message}")

def test_diagnosis_algorithm():
    """Test the diagnosis algorithm with sample data."""
    print("\n=== Testing Diagnosis Algorithm ===")
    
    # Load ICD data
    icd_data = read_csv('icd_cpt_codes_extended.csv')
    if not icd_data:
        print("✗ Could not load ICD data")
        return
    
    # Load patient data
    patient_data = read_csv('sample_patient_data.csv')
    if not patient_data:
        print("✗ Could not load patient data")
        return
    
    print(f"✓ Loaded {len(icd_data)} ICD codes and {len(patient_data)} patients")
    
    # Test diagnosis for first few patients
    for i, patient in enumerate(patient_data[:3]):
        symptoms = extract_symptoms_from_csv_row(patient)
        if symptoms:
            diagnosis, icd_code, prescription, severity, SOD, diagnosis_status, insurance = diagnose_patient(symptoms, icd_data)
            print(f"\nPatient {i+1} ({patient.get('email', 'unknown')}):")
            print(f"  Symptoms: {symptoms}")
            print(f"  Diagnosis: {diagnosis}")
            print(f"  ICD Code: {icd_code}")
            print(f"  Prescription: {prescription}")
            print(f"  Severity: {severity}")

def test_file_structure():
    """Test that all required files are present."""
    print("\n=== Testing File Structure ===")
    required_files = [
        'Diagnosis.py',
        'icd_cpt_codes_extended.csv',
        'sample_patient_data.csv',
        'templates/index.html',
        'templates/results.html'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - MISSING")

def main():
    """Run all tests."""
    print("Eye Diagnosis System - Functionality Test")
    print("=" * 50)
    
    test_file_structure()
    test_csv_reading()
    test_csv_validation()
    test_symptom_extraction()
    test_diagnosis_algorithm()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nTo run the web application:")
    print("1. python Diagnosis.py")
    print("2. Open http://localhost:5000 in your browser")
    print("3. Upload the sample_patient_data.csv file")
    print("4. Process the data to see results")

if __name__ == "__main__":
    main() 