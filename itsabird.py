import os, sys
import time
import argparse
from getpass import getpass
import requests
import json

# self documenting argument processing
def get_args():
    parser = argparse.ArgumentParser(
                 description='Find aircraft loitering within a bounding box.',
                 epilog='Alternatively, you may write user:pass to ~/.opensky')
    parser.add_argument('-u', '--username',
                 help='OpenSky Network username. Will prompt for password.')
    parser.add_argument('-c', '--count', type=int, default=4,
                 help='Count of 5 min intervals per hour for an aircraft to be considered loitering')
    parser.add_argument('-o', '--out', nargs='?', type=argparse.FileType('w'),
                 default=sys.stdout, help='redirect output to this file')
    parser.add_argument('lamin', type=float,
                 help='Min Latitude for bounding box')
    parser.add_argument('lamax', type=float,
                 help='Max Latitude for bounding box')
    parser.add_argument('lomin', type=float,
                 help='Min Longitude for bounding box')
    parser.add_argument('lomax', type=float,
                 help='Max Longitude for bounding box')

    args = parser.parse_args()

    user = args.username
    if user is None:
        # try to read from ~/.opensky
        passwd_path = os.path.join(os.path.expanduser('~'), '.opensky')
        try:
            with open(passwd_path, 'r') as f:
               user, pw = f.readline().strip(' \t\r\n').split(':', maxsplit=1)
        except:
            sys.exit('You must either provide a --username argument,\nor write username:password to ~/.opensky')
    else:
        # prompt the user for a password
        pw = getpass()

    auth = (user, pw)
    params = {'lamin':args.lamin, 'lamax':args.lamax,
              'lomin':args.lomin, 'lomax':args.lomax}
    return auth, params, args.count, args.out


def remember(memory, the_list, count):
    out = []
    to_delete = []

    # memory is a dict that contains a list of 12 ints
    for k in memory.keys():
        # roll the oldest value off the list and add the new value
        v = memory[k]
        if k in the_list:
            v = v[1:].append(1)
        else:
            v = v[1:].append(0)
        s = sum(v)
        memory[k] = v

        # find keys where we are over the limit
        if s >= count:
            out.append(k)
            to_delete.append(k)

        # forget things we haven't seen in an hour
        if s <= 0:
            to_delete.append(k)

    # delete now that we aren't iterating
    for k in to_delete:
        del memory[k]

    # add new entries to memory
    for k in the_list:
        if k not in memory.keys():
            memory[k] = [0,0,0,0,0,0,0,0,0,0,0,1]

    return memory, out


def api_once(auth, params):
    resp = requests.get('https://opensky-network.org/api/states/all',
                        auth=auth, params=params)
    js = json.loads(resp.text)
    states = js['states']
    now = int(js['time'])
    out = []

    if states is None:
        return []

    for state in states:
        # See https://openskynetwork.github.io/opensky-api/rest.html
        # These are not labeled, but columns are in this order:
        # icao_24, call_sign, origin_country, time_position, last_contact,
        # longitude, latitude, baro_altitude, on_ground, velocity, true_track,
        # vertical_rate, sensors, geo_altitude, squawk, spi, position_source,
        # category

        icao_24 = state[0]
        last_contact = int(state[4])
        on_ground = state[8]

        # ignore things on the ground
        if on_ground:
            continue

        # ignore things that haven't updated in 300 seconds
        if now - last_contact >= 300:
            continue

        # save the icao_24
        out.append(icao_24)

    return out


def main():
    auth, params, count, out = get_args()
    memory = {}

    # sleepy loop with keyboard interrupt
    try:
        while True:
            icao24_list = api_once(auth, params)
            memory, out_list = remember(memory, icao24_list, count)
            for k in out_list:
                out.write('{}\n'.format(k))
                out.flush()
            time.sleep(300)
    except KeyboardInterrupt:
        out.close()


if __name__ == '__main__':
    main()

