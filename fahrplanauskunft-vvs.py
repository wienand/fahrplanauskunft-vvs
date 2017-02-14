# -*- coding: utf-8 -*-
import collections
import datetime
import json
import os
import urllib

from flask import Flask, request

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def queryVVS():
    intent = request.json['request']['intent']
    slots = {key.lower(): data['value'] for key, data in intent['slots'].items() if 'value' in data}
    if intent['name'] == 'GetDepartures':
        result = getDepartures(**slots)
    return json.dumps(result)


def getDepartures(stop='Am Kriegsbergturm', time=None, date=None):
    url = 'http://mobile.vvs.de/jqm/controller/XSLT_DM_REQUEST?limit=20&mode=direct&type_dm=stop&useRealtime=1&outputFormat=JSON&name_dm=%s' % stop
    if time:
        url += '&itdTime=%s' % time.replace(':', '')
    if date:
        url += '&itdDate=%s' % date.replace('-', '')
    response = urllib.urlopen(url)
    response = json.loads(response.read().decode('latin1'))
    departures = collections.defaultdict(list)
    for departure in response['departureList'] or []:
        departures[(departure['servingLine']['name'], departure['servingLine']['number'], departure['servingLine']['direction'].split(' (')[0])].append(departure)
    parts = []
    now = datetime.datetime.now()
    for (name, tag, direction), departureList in departures.items():
        minutes = []
        times = []
        for departure in departureList:
            departureTime = departure.get('realDateTime', departure['dateTime'])
            departureTime = {key: int(departureTime[key]) for key in ('hour', 'month', 'year', 'day', 'minute')}
            minutesTillDepartue = (datetime.datetime(**departureTime) - now).total_seconds() / 60
            if minutesTillDepartue < 0 or minutesTillDepartue > 60:
                times += ['%d:%02d' % (departureTime['hour'], departureTime['minute'])]
            if minutesTillDepartue > 0.5:
                minutes += ['%d' % minutesTillDepartue]
            if len(minutes) > 2:
                break
        if len(minutes) > 1:
            minutes = ', '.join(minutes[:-1]) + ' und ' + minutes[-1]
        else:
            minutes = ''.join(minutes)
        if len(times) > 1:
            times = ', '.join(times[:-1]) + ' und ' + times[-1]
        else:
            times = ''.join(times)
        if minutes:
            parts += ["%s %s Richtung %s in %s Minuten" % (name, tag, direction, minutes)]
        else:
            parts += ["%s %s Richtung %s um %s Uhr" % (name, tag, direction, times)]
    result = {
        "version"          : "1.0",
        "sessionAttributes": {},
        "response"         : {
            "outputSpeech"    : {
                "type": "PlainText",
                "text": " und ".join(parts)
            },
            "shouldEndSession": True
        }
    }
    return result


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=port == 5000)
