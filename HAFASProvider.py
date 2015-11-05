#!/usr/bin/python3
from __future__ import division
from __future__ import absolute_import
import json
import urllib2, urllib
import urllib2, urllib, urlparse
import time
import calendar
import copy
from lxml import etree


class HAFASProvider(object):
    __base_uri = u'https://fahrplaner.vbn.de/bin/'

    __query_path = u'query.exe/'
    __getstop_path = u'ajax-getstop.exe/'
    __stboard_path = u'stboard.exe/'  # DTD http://fahrplaner.vbn.de/xml/hafasXMLStationBoard.dtd

    __lang = u'd'
    __type = u'n'
    __with_suggestions = u'?'  # ? = yes, ! = no

    __http_headers = {}

    __tz = u'CET'  # interprate time with this timezone

    def __init__(self):
        # http headers to send with each request

        # parse base url for Host-Header
        url = urlparse.urlparse(self.__base_uri)
        self.__http_headers[u'Host'] = url.netloc

        # disguise as a browser
        self.__http_headers[u'User-Agent'] = u'Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0'

    @staticmethod
    def __handle_station(leaf):
        info = {}
        for element in leaf:
            if element.tag == u'ExternalId':
                info[u'external_id'] = int(element.text)
                info[u'pooluic'] = int(element.get(u'pooluic'))
            elif element.tag == u'HafasName':
                text_elem = element.find(u'Text')
                info[u'name'] = text_elem.text
            else:
                print u'Unhandled Station Data ({tag}) available.'.format(tag=element.tag)

        return info

    @staticmethod
    def __handle_departure_or_arrival(leaf, start_date, start_time):
        # Note: MainStop/BasicStop will either be arrival or depature, every other PassList/BasicStop will be arrival
        timestamp = 0  # assume zero delay if delay attribute is missing
        delay = 0
        platform = -1
        for time_attr in list(leaf):
            if time_attr.tag == u'Time':
                # time is formatted as HH:MM
                timestamp = time_attr.text
                #parseable_datetime = '{date} {time} {tz}'.format(date=start_date, time=time_attr.text, tz=HAFASProvider.__tz)
                #timestamp = int(calendar.timegm(time.strptime(parseable_datetime, '%Y%m%d %H:%M %Z')))

                # if HH of the startT element is larger than the current element we
                # experienced a daychange, add 60*60*24=86400 to timestamp
                #if int(time_attr.text[:2]) < int(start_time[:2]):
                #    timestamp += 86400
            elif time_attr.tag == u'Delay':
                # convert delay to seconds, for easier calculations with unix timestamps
                delay = 60 * int(time_attr.text)
            elif time_attr.tag == u'Platform':
                # platform where the connection departs from ... strangely enough this resides under time.
                platform = time_attr.text
            else:
                print u'Unhandled time attribute ({tag} found.'.format(tag=time_attr.tag)

        return timestamp, delay, platform

    @staticmethod
    def __handle_basic_stop(leaf, start_date, start_time):
        # BasicStop
        index = int(leaf.get(u'index'))
        stop = {}
        for attr in leaf:  # BasicStop Attributes
            if attr.tag == u'Location':
                # parse location information
                x = int(attr.get(u'x'))
                y = int(attr.get(u'y'))
                lon = x / 1000000
                lat = y / 1000000
                type = attr.get(u'type')

                # get generic station information
                for st in attr:  # Station
                    stop = HAFASProvider.__handle_station(st)

                    # append location data to station_info
                    location = {u'lat': lat, u'lon': lon, u'x': x, u'y': y, u'type': type}
                    stop[u'location'] = location

            elif attr.tag == u'Dep' or attr.tag == u'Arr':
                stop[u'time'], stop[u'delay'], stop[u'platform'] = HAFASProvider.__handle_departure_or_arrival(attr, start_date, start_time)

            else:
                print u'Unhandled BasicStop child ({tag}) found.'.format(tag=attr.tag)
        return index, stop


    def get_stboard(self, query, when=u'actual', discard_nearby=u'yes', max_results=u'50', products=u'11111111111',
                    type=u'dep'):
        u'''
        returns a tuple with (station_info, connections)
        '''

        # request params defaults
        query_param = {}
        #query_param['L'] = 'vs_rmv.vs_sq'  # Layout (affects web form output)
        #query_param['L'] = 'vs_java3' # seems to be a generic layout available in every installation
        query_param[u'selectDate'] = u'today'  # Day (yesterday, today)
        query_param[u'time'] = when # Time (use 'actual' for now or 'HHMM')
        query_param[u'input'] = query  # Search Query (can be a String or Integer (ExternalId))
        query_param[u'disableEquivs'] = discard_nearby # Don't use nearby stations
        query_param[u'maxJourneys'] = max_results # Maximal number of results
        query_param[u'boardType'] = type # Departure / Arrival
        query_param[u'productsFilter'] = products # Means of Transport (skip or 11111111111 for all)
        query_param[u'maxStops'] = 10  # max amount of intermediate stops for each connection
        query_param[u'rt'] = 1  # Enable Realtime-Data
        query_param[u'start'] = u'yes'  # Start Query or Webform
        # UNUSED / UNTESTED AT THIS POINT
        # inputTripelId (sic!)  Direct Reference to a Station as returned by the undocumented station search
        # inputRef              Refer to station by <stationName>#<externalId>
        query_param[u'output'] = u'xml'  # Output Format (auto fallback to some html website)

        qp = urllib.urlencode(query_param)

        # request
        req_uri = u"{base_uri}{binary_path}{lang}{type}{suggestions}{query_params}".format(base_uri=self.__base_uri, \
            lang=self.__lang, type=self.__type, suggestions=self.__with_suggestions, \
            query_params=qp, binary_path=self.__stboard_path)
        #print(req_uri)
        req = urllib2.Request(req_uri)
        self.__add_http_headers(req)
        res = urllib2.urlopen(req)
        data = res.read()

        # xml handling
        root = etree.fromstring(data)

        # get start time to calculate the day and detect daychanges
        start_date = root.find(u"SBRes/SBReq/StartT").get(u"date")
        start_time = root.find(u"SBRes/SBReq/StartT").get(u"time")

        # station that hafas selected
        origin_station = list(root.find(u"SBRes/SBReq/Start/Station"))
        try:
            origin_station_info = self.__handle_station(origin_station)
        except TypeError:
            raise StationNotFoundException

        connections = []
        for journey in root.findall(u'SBRes/JourneyList/Journey'):  # Journey
            # connection-level
            conn = {u'train_id': journey.get(u'trainId')}
            stops = {}

            for elem in list(journey):
                if elem.tag == u'JourneyAttributeList':
                    # JourneyAttributeList
                    for journey_attr in list(elem):  # JourneyAttribute
                        # attribute validity
                        valid_from = journey_attr.get(u'from')
                        valid_to = journey_attr.get(u'to')
                        for attr in list(journey_attr):  # Attribute
                            # attribute description and priority
                            priority = attr.get(u'priority')
                            type = attr.get(u'type').lower()
                            conn[type] = {}
                            for attr_type in list(attr):  # AttributeCode, AttributeVariant
                                # the actual data stuff,
                                # AttributeCode is usually a numeric representation of AttributeVariant
                                if attr_type.tag == u'AttributeCode':
                                    variant_code = attr_type.text
                                    conn[type][u'code'] = variant_code
                                elif attr_type.tag == u'AttributeVariant':
                                    variant_type = attr_type.get(u'type').lower()
                                    for text_field in attr_type:
                                        value = text_field.text
                                        conn[type][variant_type] = value
                                else:
                                    print u'Unhandled attribute type ({tag}) found.'.format(tag=attr_type.tag)

                elif elem.tag == u'MainStop':
                    # MainStop
                    # departure station, will match selected station, but may be different if disableEquivs=no
                    for stop in list(elem):
                        index, stop = self.__handle_basic_stop(stop, start_date, start_time)

                        # Directly write back time/delay to connection, because this is the MainStop/BasicStop,
                        # do not do this in PassList/BasicStop
                        conn[u'time'] = stop[u'time']
                        conn[u'delay'] = stop[u'delay']

                        # Also write back location to origin station if external_id and pooluic match
                        if stop[u'external_id'] == origin_station_info[u'external_id'] and \
                           stop[u'pooluic'] == origin_station_info[u'pooluic']:
                            origin_station_info[u'location'] = stop[u'location']

                        stops[index] = stop

                elif elem.tag == u'Product':
                    # Product
                    # information is redundant with JourneyAttribute type='name'
                    pass

                elif elem.tag == u'PassList':
                    # PassList
                    for stop in list(elem):
                        index, stop = self.__handle_basic_stop(stop, start_date, start_time)
                        stops[index] = stop

                elif elem.tag == u'InfoTextList':
                    # InfoTextList
                    # some additional commentary on the route
                    conn[u'infotext'] = []
                    for infotext in elem:
                        info = {u'title': infotext.get(u'text'), u'text': infotext.get(u'textL')}
                        conn[u'infotext'].append(info)

                else:
                    print u'Unhandled Journey child ({tag}) found.'.format(tag=elem.tag)

            conn[u'stops'] = stops
            connections.append(conn)

        return origin_station_info, connections

    def __add_http_headers(self, request):
        for header, value in self.__http_headers.items():
            request.add_header(header, value)

    def get_nearby_stations(self, x, y, max=25, dist=5000):
        # x = lon / 1000000, y = lat / 10000000
        #print("X: {} Y: {}".format(x, y))

        # parameters
        query_param = {}
        query_param[u'performLocating'] = 2
        query_param[u'tpl'] = u'stop2json'
        query_param[u'look_maxno'] = max
        query_param[u'look_maxdist'] = dist
        query_param[u'look_nv'] = u'get_stopweight|yes'
        query_param[u'look_x'] = x
        query_param[u'look_y'] = y
        qp = urllib.urlencode(query_param)

        # request
        req_uri = u"{base_uri}{binary_path}{lang}{type}y{suggestions}{query_params}".format(base_uri=self.__base_uri, \
            lang=self.__lang, type=self.__type, suggestions=self.__with_suggestions, \
            query_params=qp, binary_path=self.__query_path)
        print req_uri
        req = urllib2.Request(req_uri)
        self.__add_http_headers(req)
        res = urllib2.urlopen(req)
        data = res.read()
        data = data.decode(u'utf-8')

        root = json.loads(data)
        stops = []
        for stop in root[u'stops']:
            stops.append({u'name': stop[u'name'],
                          u'external_id': int(stop[u'extId']),
                          u'pooluic': int(stop[u'puic']),
                          u'lat': int(stop[u'y']) / 1000000,
                          u'lon': int(stop[u'x']) / 1000000,
                          u'dist': int(stop[u'dist']),
                          u'weight': int(stop[u'stopweight']),
                          u'products': int(stop[u'prodclass'])})

        return stops

    def get_autocomplete_locations(self, query, max=25):
        # parameters
        query_param = {}
        query_param[u'getstop'] = 1
        query_param[u'REQ0JourneyStopsS0A'] = max
        query_param[u'REQ0JourneyStopsS0G'] = query
        qp = urllib.urlencode(query_param)

        # request
        req_uri = u"{base_uri}{binary_path}{lang}{type}{suggestions}{query_params}".format(base_uri=self.__base_uri, \
            lang=self.__lang, type=self.__type, suggestions=self.__with_suggestions, \
            query_params=qp, binary_path=self.__getstop_path)
        print req_uri
        req = urllib2.Request(req_uri)
        self.__add_http_headers(req)
        res = urllib2.urlopen(req)
        data = res.read()
        data = data.decode(u'utf-8')

        begin = data.find(u'{')
        end = data.rfind(u'}')
        root = json.loads(data[begin:end+1])

        stops = []
        for stop in root[u'suggestions']:
            try:
                stops.append({u'name': stop[u'value'],
                              u'external_id': stop[u'extId'],
                              u'lat': int(stop[u'ycoord']) / 1000 if stop[u'ycoord'].isdigit() else None,
                              u'lon': int(stop[u'xcoord']) / 1000 if stop[u'xcoord'].isdigit() else None,
                              u'weight': int(stop[u'weight']),
                              u'products': stop[u'prodClass'],
                              u'type': stop[u'type']})
            except KeyError, e:
                print u"Caught KeyError in get_autocomplete_location: {}".format(e)

        return sorted(stops, key = lambda stop: stop[u'weight'], reverse=True)


class HAFASException(Exception):
    pass

class StationNotFoundException(HAFASException):
    pass

