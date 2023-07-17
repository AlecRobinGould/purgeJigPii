#!/bin/bash
# If you see the ADC timeout errors, you can add a sleep. This will allow time for CPU
# resources to free up. I fixed the timeout errors now.
# sleep 15
screen -m -d -S purge bash -c 'python /home/antlabpi/purgeJig/purgeJigPii/purge.py; exec bash'