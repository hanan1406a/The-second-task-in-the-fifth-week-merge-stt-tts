

import argparse
import base64
import configparser
import json
import threading
import time
from playsound import playsound
import pyaudio
import websocket
from websocket._abnf import ABNF


from ibm_watson.websocket import SynthesizeCallback
from ibm_watson import TextToSpeechV1
from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

 #Setup TTS service 
authenticator = IAMAuthenticator('FRzGcl1deop2G9Gxg3RkpHHI8KHADgDxfjRSrfMJ8sm3') 
tts = TextToSpeechV1(authenticator=authenticator)
tts.set_service_url('https://api.us-east.text-to-speech.watson.cloud.ibm.com/instances/c48e94a4-9dbd-491c-ab6c-3cc1403ffb32')

#Setup Assistant service
authenticator = IAMAuthenticator('L8qTsPwPcqlYNIGpgOplE_tn_pvgat9SMVV7FcMLnt1k')
assistant = AssistantV2(version='2020-04-01', authenticator = authenticator)
assistant.set_service_url('https://api.eu-gb.assistant.watson.cloud.ibm.com/instances/59c70c2e-b9dc-4109-9591-e33230f375bc')

CHUNK = 1024
FORMAT = pyaudio.paInt16

CHANNELS = 1

RATE = 44100
RECORD_SECONDS = 5
FINALS = []
LAST = None

REGION_MAP = {
    'us-east': 'gateway-wdc.watsonplatform.net',
    'us-south': 'stream.watsonplatform.net',
    'eu-gb': 'stream.watsonplatform.net',
    'eu-de': 'stream-fra.watsonplatform.net',
    'au-syd': 'gateway-syd.watsonplatform.net',
    'jp-tok': 'gateway-syd.watsonplatform.net',
}


def read_audio(ws, timeout):
    """Read audio and sent it to the websocket port.
    This uses pyaudio to read from a device in chunks and send these
    over the websocket wire.
    """
    global RATE
    p = pyaudio.PyAudio()
   
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording")
    rec = timeout or RECORD_SECONDS

    for i in range(0, int(RATE / CHUNK * rec)):
        data = stream.read(CHUNK)
     
        ws.send(data, ABNF.OPCODE_BINARY)

    stream.stop_stream()
    stream.close()
    print("* done recording")

    
    data = {"action": "stop"}
    ws.send(json.dumps(data).encode('utf8'))
   
    time.sleep(1)
    ws.close()

   
    p.terminate()



   def on_message(self, msg):
        """Print whatever messages come in.
    While we are processing any non trivial stream of speech Watson
    will start chunking results into bits of transcripts that it
    considers "final", and start on a new stretch. It's not always
    clear why it does this. However, it means that as we are
    processing text, any time we see a final chunk, we need to save it
    off for later.
    """
    global LAST
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        # This prints out the current fragment that we are working on
        output_text = data['results'][0]['alternatives'][0]['transcript']
        print(output_text)
        #STT
        with open ('result.txt','w') as text:
          text.writelines(output_text)
          text.close()
        print (json.dumps(response, indent=2))
        
def on_error(self, error):
    """Print any errors."""
    print(error)


def on_close(ws):
    """Upon close, print the complete and final transcript."""
    global LAST
    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    print(transcript)


def on_open(ws):
    """Triggered as soon a we have an active connection."""
    args = ws.args
    data = {
        "action": "start",
        
        "content-type": "audio/l16;rate=%d" % RATE,
        "continuous": True,
        "interim_results": True,
        
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 3
    }

    
    ws.send(json.dumps(data).encode('utf8'))
 
    threading.Thread(target=read_audio,
                     args=(ws, args.timeout)).start()

def get_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    
    region = config.get('auth', 'region')
    host = REGION_MAP[region]
    return ("wss://{}/speech-to-text/api/v1/recognize"
           "?model=en-US_BroadbandModel").format(host)

def get_auth():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    apikey = config.get('auth', 'apikey')
    return ("apikey", apikey)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Transcribe Watson text in real time')
    parser.add_argument('-t', '--timeout', type=int, default=5)
    
    args = parser.parse_args()
    return args


def main():
   
    headers = {}
    userpass = ":".join(get_auth())
    headers["Authorization"] = "Basic " + base64.b64encode(
        userpass.encode()).decode()
    url = get_url()

    
             
    ws = websocket.WebSocketApp(url,
                                header=headers,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.args = parse_args()
   
   
    ws.run_forever()
    
    
    with open('result.txt', 'r') as f:
     tts_Speech = f.readlines()
     tts_Speech = [line.replace('\n', '') for line in tts_Speech]
     tts_Speech = ''.join(str(line) for line in tts_Speech)
     
    #Respons Assistant
    response = assistant.message_stateless(
     assistant_id='2077b151-1b7e-4e43-b72b-4401c495603b', 
     input={ 'message_type': 'text',  'text': tts_Speech }
    ).get_result()
    text   = json.dumps(response, indent=2)
    write  = json.loads(text)
    speech = json.dumps(write["output"]["generic"][0].get("text"))
    with open('speech.mp3', 'wb') as a:
      res = tts.synthesize(speech, accept='speecho/mp3', voice='en-US_AllisonV3Voice').get_result()
      a.write(res.content)
      a.close() 
    print(speech) 
    playsound('speech.mp3') 
  
if __name__ == "__main__":
    main()
