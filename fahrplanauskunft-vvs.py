# -*- coding: utf-8 -*-
import collections
import datetime
import json
import os
import urllib

from flask import Flask, request

port = int(os.environ.get("PORT", 5000))
runsAtHeroku = port != 5000
app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def queryVVS():
    intent = request.json['request']['intent']
    slots = {key.lower(): data['value'] for key, data in intent['slots'].items() if 'value' in data}
    if intent['name'] == 'GetDepartures':
        result = getDepartures(**slots)
    elif intent['name'] == 'GetConnection':
        result = getConnection(**slots)
    return json.dumps(result)


def getConnection(source='Am Kriegsbergturm', target='Hauptbahnhof', time=None, date=None):
    url = 'http://mobil.vvs.de/jqm/controller/XSLT_TRIP_REQUEST2?outputFormat=JSON&type_destination=stop&type_origin=stop&useRealtime=1&name_origin=%s&name_destination=%s' \
          % (urllib.quote_plus(source.encode('utf8')), urllib.quote_plus(target.encode('utf8')))
    if time:
        url += '&itdTime=%s' % time.replace(':', '')
    if date:
        url += '&itdDate=%s' % date.replace('-', '')
    response = urllib.urlopen(url)
    response = json.loads(response.read().decode('latin1'))
    trips = []
    now = datetime.datetime.now()
    for trip in response['trips'] or []:
        hours, minutes = (int(x) for x in trip['duration'].split(':'))
        tripText = 'Fahrzeit'
        if hours:
            tripText += ' %d Stunden und' % hours
        tripText += ' %d Minuten' % minutes
        interchanges = int(trip['interchange'])
        if interchanges:
            if interchanges == 1:
                tripText += ' bei einem Umstieg'
            else:
                tripText += ' bei %d Umstiegen' % interchanges
        firstLeg = True
        for leg in trip['legs']:
            if firstLeg:
                firstLeg = False
                dateTime = leg['points'][0]['dateTime']
                departureTime = datetime.datetime.strptime(dateTime.get('rtDate', dateTime['date']) + ' ' + dateTime.get('rtTime', dateTime['time']), '%d.%m.%Y %H:%M')
                minutesTillDeparture = (departureTime - now).total_seconds() / 60
                if runsAtHeroku:
                    minutesTillDeparture -= 60
                if minutesTillDeparture < 0.5 or minutesTillDeparture > 60:
                    tripText += ' mit %s in Richtung %s ab %s Uhr bis %s' % (leg['mode']['name'], leg['mode']['destination'].split(' (')[0], dateTime.get('rtTime', dateTime['time']), leg['points'][-1]['name'])
                elif minutesTillDeparture > 0.5:
                    tripText += ' mit %s in Richtung %s in %d Minuten bis %s' % (leg['mode']['name'], leg['mode']['destination'].split(' (')[0], minutesTillDeparture, leg['points'][-1]['name'])
            else:
                dateTime = leg['points'][0]['dateTime']
                departureTime = datetime.datetime.strptime(dateTime.get('rtDate', dateTime['date']) + ' ' + dateTime.get('rtTime', dateTime['time']), '%d.%m.%Y %H:%M')
                minutesForInterchange = (departureTime - lastArrivalTime).total_seconds() / 60
                tripText += ', dann in %d Minuten umsteigen in %s Richtung %s bis %s' % (minutesForInterchange, leg['mode']['name'], leg['mode']['destination'].split(' (')[0], leg['points'][-1]['name'])
            dateTime = leg['points'][-1]['dateTime']
            lastArrivalTime = datetime.datetime.strptime(dateTime.get('rtDate', dateTime['date']) + ' ' + dateTime.get('rtTime', dateTime['time']), '%d.%m.%Y %H:%M')
        trips.append(tripText)

    result = {
        "version"          : "1.0",
        "sessionAttributes": {},
        "response"         : {
            "outputSpeech"    : {
                "type": "PlainText",
                "text": ". ".join(trips)
            },
            "shouldEndSession": True
        }
    }
    return result


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
            minutesTillDeparture = (datetime.datetime(**departureTime) - now).total_seconds() / 60
            if runsAtHeroku:
                minutesTillDeparture -= 60
            if minutesTillDeparture < 0.5 or minutesTillDeparture > 60:
                times += ['%d:%02d' % (departureTime['hour'], departureTime['minute'])]
            elif minutesTillDeparture > 0.5:
                minutes += ['%d' % minutesTillDeparture]
            if len(minutes) + len(times) > 2:
                break
        if len(minutes) > 1:
            minutes = ', '.join(minutes[:-1]) + ' und ' + minutes[-1]
        else:
            minutes = ''.join(minutes)
        if len(times) > 1:
            times = ', '.join(times[:-1]) + ' und ' + times[-1]
        else:
            times = ''.join(times)
        part = '%s %s Richtung %s ' % (name, tag, direction)
        if minutes:
            part += "in %s Minuten" % minutes
        if times:
            if minutes:
                part += ' und '
            part += "um %s Uhr" % times
        parts.append(part)
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
    if runsAtHeroku:
        app.run(host='0.0.0.0', port=port)
    else:
        app.run(debug=True)
