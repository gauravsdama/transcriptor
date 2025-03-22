# transcriptor
# AssemblyAI Audio Transcription

This project demonstrates how to upload an audio file to AssemblyAI, transcribe it, and save the resulting transcript to a text file. The script uses the AssemblyAI API to handle file uploads and transcription requests, polling until the transcription is complete.

> **DISCLAIMER:** This project is provided for educational and research purposes only. Be sure to comply with AssemblyAI's terms of service and all applicable laws when using this code.

## Features

- **File Upload:**  
  Reads and uploads an audio file in chunks to AssemblyAI.

- **Transcription Request:**  
  Sends a transcription request to the AssemblyAI API.

- **Polling Mechanism:**  
  Periodically checks the transcription status until it is complete or an error occurs.

- **Transcript Saving:**  
  Saves the transcribed text to a file.

## Prerequisites

- **Python 3.x**
- **Dependencies:**  
  - `requests` (Install via `pip install requests`)
  - Standard libraries: `time`, `os`

- **AssemblyAI API Key:**  
  You need an AssemblyAI API key. Create a file named `api_secret.py` in your project directory containing:
  ```python
  # api_secret.py
  API_KEY_ASSEMBLYAI = "your_assemblyai_api_key_here"
