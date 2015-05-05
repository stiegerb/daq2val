#!/usr/bin/env python

#----------------------------------------------------------------------

comments = {
    "# missing network card": [ "bu-c2f16-37-01", "bu-c2f16-41-01" ],
    }

blackList = [
    "ru-c2e12-26-01",
    "ru-c2e13-25-01",
    "ru-c2e13-35-01",
    "ru-c2e15-26-01",
    "bu-c2e18-27-01",
    "bu-c2e18-29-01",
    "bu-c2e18-31-01",
    "bu-c2e18-35-01",
    "bu-c2e18-37-01",
    "bu-c2e18-39-01",
    "bu-c2e18-41-01",
    "bu-c2e18-43-01",
    "bu-c2f16-27-01",
    "bu-c2f16-29-01",
    "bu-c2f16-31-01",
    "bu-c2f16-35-01",
    "bu-c2f16-37-01",
    "bu-c2f16-39-01",
    "bu-c2f16-41-01",
    "bu-c2f16-43-01",
    ]

#----------------------------------------------------------------------
import sys


for index,line in enumerate(sys.stdin.readlines()):
    line = line.split('\n')[0]

    parts = line.split(',')

    assert len(parts) <= 4

    if index == 0:
        # header line
        assert len(parts) == 4
        parts.extend(['Blacklist', 'Comment'])

    else:
        while len(parts) < 4:
            parts.append("")

        host = parts[2]

        # the following is not super efficient but should be sufficient for us

        #----------
        # blacklist
        #----------
        if host in blackList:
            parts.append(1)
        else:
            parts.append(0)

        #----------
        # comments
        #----------
        allComments = []

        for comment, hostList in comments.items():
            if host in hostList:
                allComments.append(comment)

        if allComments:
            parts.append(";".join(allComments))




    print ",".join([str(x) for x in parts ])
