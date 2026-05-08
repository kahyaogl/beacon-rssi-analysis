A_REF = -53.5
N = 2.8

def calculate_distance(rssi):
    return 10 ** ((A_REF - rssi) / (10 * N))