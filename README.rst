pymqttbench
===========

This is a tool to benchmark the performance of an mqtt broker. It works by
launching an arbitrary number of publishers and subscribers in parallel. These
workers both publish and subscribe to the same topic and either send or recieve
a fixed number of messages.


Installation
------------

To install pymqttbench you need to clone the repo with::

    https://github.com/mtreinish/handbrakecloud.git

then install it using pip::

    pip install handbrakecloud

Alternatively you can run::

    cd handbrakecloud && python setup.py install

however using pip is recommended.

Usage
-----

After installing pymqttbench you simply run it with the::

    pymqttbench --hostname $BROKER_HOST

command. The hostname parameter is required to tell pymqttbench the hostname
of the broker. This is the only required field, but there are several other
options exposed for how to connect to the broker. ``--port`` is used to specify
the port if you're not connecting on the standard port, ``1883``. ``--username``
and ``--password`` are used to specify user authentication if needed. Similiarly
``--cacert`` can be used to specify a trusted CA certificate to verify the TLS
connection on the broker. There is also the ``--topic`` parameter which
is used to specify a topic to use for the benchmark, by default *pybench* is
used. Note that all of these settings are used for both the publishers and
subscribers.

Outside of mqtt connection options there is also the ``--brief`` flag which is
used to print a colon separated list of benchmark results instead of the default
human readable formatted output. The format for this output is::

    Subscriber Count:Publisher Count:Subscriber Mean Duration:Subscriber Duration Std. Deviation:Subscriber Avg. Throughput:Subscriber Total Throughput:Publisher Mean Duration:Publisher Duration Std. Deviation:Publisher Avg. Throughput:Publisher Total Throughput

Tuning the benchmark
''''''''''''''''''''

After pymqttbench knows how to connect to the broker you can tune the benchmark
to your specific needs. There are several axes you can adjust the bechmark on,
the first being the number of publishers and subscribers. This is configurable
with the ``--pub-clients`` and ``--sub-clients`` flags. By default each is set
to *10*. The next option you can tune is the number of messages that the
publishers will send, with ``--pub-count``, and the number of messages the
subscribers will listen for, with ``--sub-count``. It's worth pointing out that
the subscribers do not pair with an individual worker like in some other
benchmarking tools, but instead listen to the same topic that all the publishers
publish to. In addition with adjusting these options you'll likely want to
change the publisher timeout, ``--pub-timeout``, and the subscriber timeout,
``sub-timeout``, which describe how long the benchmark will wait for the worker
to either publish or recieve the specified message count.

You can also set how large the message payload is with ``--msg-size`` which
takes the number of bytes to use. By default it uses a 1024 byte payload. The
last tuning option is ``--qos`` which is used to specify the qos level to use
for benchmarking. By default qos 0 is used.
