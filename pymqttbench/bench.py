# Copyright 2017 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import datetime
import multiprocessing
import random
import string
import time

import numpy
import paho.mqtt.client as mqtt
from paho.mqtt import publish

BASE_TOPIC = 'pybench'

SUB_QUEUE = multiprocessing.Queue()
PUB_QUEUE = multiprocessing.Queue()


class Sub(multiprocessing.Process):
    def __init__(self, hostname, port=1883, tls=None, auth=None, topic=None,
                 timeout=60, max_count=10, qos=0):
        super(Sub, self).__init__()
        self.hostname = hostname
        self.port = port
        self.tls = tls
        self.topic = topic or BASE_TOPIC
        self.auth = auth
        self.msg_count = 0
        self.start_time = None
        self.max_count = max_count
        self.end_time = None
        self.timeout = timeout
        self.qos = qos
        self.end_time_lock = multiprocessing.Lock()

    def run(self):
        def on_connect(client, userdata, flags, rc):
            client.subscribe(BASE_TOPIC + '/#', qos=self.qos)

        def on_message(client, userdata, msg):
            if self.start_time is None:
                self.start_time = datetime.datetime.utcnow()
            self.msg_count += 1
            if self.msg_count >= self.max_count:
                self.end_time_lock.acquire()
                if self.end_time is None:
                    self.end_time = datetime.datetime.utcnow()
                self.end_time_lock.release()

        self.client = mqtt.Client()
        self.client.on_connect = on_connect
        self.client.on_message = on_message
        if self.tls:
            self.client.tls_set(**self.tls)
        if self.auth:
            self.client.username_pw_set(**self.auth)
        self.client.connect(self.hostname, port=self.port)
        self.client.loop_start()
        while True:
            time.sleep(1)
            self.end_time_lock.acquire()
            if self.end_time:
                delta = self.end_time - self.start_time
                SUB_QUEUE.put(delta.total_seconds())
                self.client.loop_stop()
                break
            self.end_time_lock.release()
            if self.start_time:
                current_time = datetime.datetime.utcnow()
                curr_delta = current_time - self.start_time
                if curr_delta.total_seconds() > self.timeout:
                    raise Exception('We hit the sub timeout!')


class Pub(multiprocessing.Process):
    def __init__(self, hostname, port=1883, tls=None, auth=None, topic=None,
                 timeout=60, max_count=10, msg_size=1024, qos=0):
        super(Pub, self).__init__()
        self.hostname = hostname
        self.port = port
        self.tls = tls
        self.topic = topic or BASE_TOPIC
        self.auth = auth
        self.start_time = None
        self.max_count = max_count
        self.end_time = None
        self.timeout = timeout
        self.msg = ''.join(
            random.choice(string.lowercase) for i in range(msg_size))
        self.qos = qos

    def run(self):
        self.start_time = datetime.datetime.utcnow()
        for i in range(self.max_count):
            publish.single(self.topic, self.msg, hostname=self.hostname,
                           port=self.port, auth=self.auth, tls=self.tls,
                           qos=self.qos)
            if self.start_time:
                current_time = datetime.datetime.utcnow()
                curr_delta = current_time - self.start_time
                if curr_delta.total_seconds() > self.timeout:
                    raise Exception('We hit the pub timeout!')
        end_time = datetime.datetime.utcnow()
        delta = end_time - self.start_time
        PUB_QUEUE.put(delta.total_seconds())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pub-clients', type=int, dest='pub_clients',
                        default=10,
                        help='The number of publisher client workers to use. '
                             'By default 10 are used.')
    parser.add_argument('--sub-clients', type=int, dest='sub_clients',
                        default=10,
                        help='The number of subscriber client workers to use. '
                             'By default 10 are used')
    parser.add_argument('--pub-count', type=int, dest='pub_count',
                        default=10,
                        help='The number of messages each publisher client '
                             'will publish for completing. The default count '
                             'is 10')
    parser.add_argument('--sub-count', type=int, dest='sub_count',
                        default=10,
                        help='The number of messages each subscriber client '
                             'will wait to recieve before completing. The '
                             'default count is 10.')
    parser.add_argument('--msg-size', type=int, dest='msg_size', default=1024,
                        help='The payload size to use in bytes')
    parser.add_argument('--sub-timeout', type=int, dest='sub_timeout',
                        default=60,
                        help='The amount of time, in seconds, a subscriber '
                             'client will wait for messages. By default this '
                             'is 60.')
    parser.add_argument('--pub-timeout', type=int, dest='pub_timeout',
                        default=60,
                        help="The amount of time, in seconds, a publisher "
                             "client will wait to successfully publish it's "
                             "messages. By default this is 60")
    parser.add_argument('--hostname', required=True,
                        help='The hostname (or ip address) of the broker to '
                             'connect to')
    parser.add_argument('--port', default=1883, type=int,
                        help='The port to use for connecting to the broker. '
                             'The default port is 1883.')
    parser.add_argument('--topic',
                        help='The MQTT topic to use for the benchmark. The '
                             'default topic is pybench')
    parser.add_argument('--cacert',
                        help='The certificate authority certificate file that '
                             'are treated as trusted by the clients')
    parser.add_argument('--username',
                        help='An optional username to use for auth on the '
                             'broker')
    parser.add_argument('--password',
                        help='An optional password to use for auth on the '
                             'broker. This requires a username is also set')
    parser.add_argument('--brief', action='store_true', default=False,
                        help='Print results in a colon separated list instead'
                             ' of a human readable format. See the README for '
                             'the order of results in this format')
    parser.add_argument('--qos', default=0, type=int, choices=[0, 1, 2],
                        help='The qos level to use for the benchmark')

    opts = parser.parse_args()

    sub_threads = []
    pub_threads = []

    topic = getattr(opts, 'topic') or BASE_TOPIC
    tls = None
    if getattr(opts, 'cacert'):
        tls = {'ca_certs': opts.cacert}

    auth = None
    if opts.username:
        auth = {'username': opts.username,
                'password': getattr(opts, 'password')}

    if opts.pub_count * opts.pub_clients < opts.sub_count:
        print('The configured number of publisher clients and published '
              'message count is too small for the configured subscriber count.'
              ' Increase the value of --pub-count and/or --pub-clients, or '
              'decrease the value of --sub-count.')
        exit(1)

    for i in range(opts.sub_clients):
        sub = Sub(opts.hostname, opts.port, tls, auth, topic, opts.sub_timeout,
                  opts.sub_count, opts.qos)
        sub_threads.append(sub)
        sub.start()

    for i in range(opts.pub_clients):
        pub = Pub(opts.hostname, opts.port, tls, auth, topic, opts.pub_timeout,
                  opts.pub_count, opts.qos)
        pub_threads.append(pub)
        pub.start()

    start_timer = datetime.datetime.utcnow()
    for client in sub_threads:
        client.join(opts.sub_timeout)
        curr_time = datetime.datetime.utcnow()
        delta = start_timer - curr_time
        if delta.total_seconds() >= opts.sub_timeout:
            raise Exception('Timed out waiting for threads to return')

    start_timer = datetime.datetime.utcnow()
    for client in pub_threads:
        client.join(opts.pub_timeout)
        curr_time = datetime.datetime.utcnow()
        delta = start_timer - curr_time
        if delta.total_seconds() >= opts.sub_timeout:
            raise Exception('Timed out waiting for threads to return')

    # Let's do some maths
    if SUB_QUEUE.qsize < opts.sub_clients:
        print('Something went horribly wrong, there are less results than '
              'sub threads')
        exit(1)
    if PUB_QUEUE.qsize < opts.pub_clients:
        print('Something went horribly wrong, there are less results than '
              'pub threads')
        exit(1)

    sub_times = []
    for i in range(opts.sub_clients):
        try:
            sub_times.append(SUB_QUEUE.get(opts.sub_timeout))
        except multiprocessing.queues.Empty:
            continue
    if len(sub_times) < opts.sub_clients:
        failed_count = opts.sub_clients - len(sub_times)
    sub_times = numpy.array(sub_times)

    pub_times = []
    for i in range(opts.pub_clients):
        try:
            pub_times.append(PUB_QUEUE.get(opts.pub_timeout))
        except multiprocessing.queues.Empty:
            continue
    if len(pub_times) < opts.pub_clients:
        failed_count = opts.pub_clients - len(pub_times)
    pub_times = numpy.array(pub_times)

    if len(sub_times) < opts.sub_clients:
        failed_count = opts.sub_clients - len(sub_times)
        print("%s subscription workers failed" % failed_count)
    if len(pub_times) < opts.pub_clients:
        failed_count = opts.pub_clients - len(pub_times)
        print("%s publishing workers failed" % failed_count)

    sub_mean_duration = numpy.mean(sub_times)
    sub_avg_throughput = float(opts.sub_count) / float(sub_mean_duration)
    sub_total_thpt = float(
        opts.sub_count * opts.sub_clients) / float(sub_mean_duration)
    pub_mean_duration = numpy.mean(pub_times)
    pub_avg_throughput = float(opts.pub_count) / float(pub_mean_duration)
    pub_total_thpt = float(
        opts.pub_count * opts.pub_clients) / float(pub_mean_duration)
    if opts.brief:
        output = '%s:%s:%s:%s:%s:%s:%s:%s:%s:%s'
    else:
        output = """\
[ran with %s subscribers and %s publishers]
================================================================================
Subscription Results
================================================================================
Avg. subscriber duration: %s
Subscriber duration std dev: %s
Avg. Client Throughput: %s
Total Throughput (msg_count * clients) / (avg. sub time): %s
================================================================================
Publisher Results
================================================================================
Avg. publisher duration: %s
Publisher duration std dev: %s
Avg. Client Throughput: %s
Total Throughput (msg_count * clients) / (avg. sub time): %s
"""
    print(output % (
        opts.sub_clients,
        opts.pub_clients,
        sub_mean_duration,
        numpy.std(sub_times),
        sub_avg_throughput,
        sub_total_thpt,
        pub_mean_duration,
        numpy.std(pub_times),
        pub_avg_throughput,
        pub_total_thpt,
        ))


if __name__ == '__main__':
    main()
