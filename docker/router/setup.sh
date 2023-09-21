# Delete default route to avoid interference when interface goes up/down
ip route del default

# Start ifplugd
#/usr/sbin/ifplugd -a -i eth1 -q -f -u0 -d0 -I -r /root/project/eth1-updown
#./eth1-updown eth1 up
