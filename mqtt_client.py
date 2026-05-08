import paho.mqtt.client as mqtt
from utils.queue_manager import data_queue

BROKER =  "5.253.140.60"
PORT = 1883
TOPIC = "espresense/devices/#"

def on_message(client,userdata,msg):
    payload = msg.payload.decode()
    data_queue.put((msg.topic ,payload))
    
    
def start():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(BROKER, 1883,60)
    client.subscribe(TOPIC)
    client.loop_start()