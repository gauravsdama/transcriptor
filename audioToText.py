import requests
from api_secret import API_KEY_ASSEMBLYAI
import time

#upload
upload_endpoint = "https://api.assemblyai.com/v2/upload"
transcript_endpoint = "https://api.assemblyai.com/v2/transcript"
filename = "audio01.wav"
headers = {'authorization': API_KEY_ASSEMBLYAI }

def upload():
    def read_file(filename, chunk_size=5242880):
        with open(filename, 'rb') as _file:
            while True:
                data = _file.read(chunk_size)
                if not data:
                    break
                yield data
    
    up_response = requests.post('https://api.assemblyai.com/v2/upload',
                                headers=headers,
                                data=read_file(filename))
    audio_url = up_response.json()['upload_url']
    print(audio_url)
    return audio_url

#transcribe
def transcribe(audio_url):
    tr_request = { "audio_url": audio_url }
    tr_response = requests.post(transcript_endpoint, json=tr_request, headers=headers)
    job_id = tr_response.json()['id']
    return job_id



#poll
def poll(audio_job_id):
    polling_endpoint = transcript_endpoint + '/' + audio_job_id
    polling_response = requests.get(polling_endpoint, headers=headers)
    return polling_response.json()

def get_transcription_result_url(audio_link):
    transcript_id = transcribe(audio_link)
    while True:
        data = poll(transcript_id)
        if data['status'] == 'completed':
            return data, None
        elif data['status'] == 'error':
            return data, data['error']
        print('Waiting 10 seconds...')
        time.sleep(10)

#save transcipt file
def save_trascript(audio_link):
    data, error = get_transcription_result_url(audio_link)

    if data:
        transcript_filename = filename + ".txt"
        with open(transcript_filename, "w") as f:
            f.write(data['text'])
        print('Transcription saved !')
    elif error:
        print("error !", error)

#upload the file
audio_link = upload()

save_trascript(audio_link)
               

