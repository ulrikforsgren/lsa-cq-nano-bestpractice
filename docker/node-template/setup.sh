# Delete default route to avoid interference when interface goes up/down
ip route del default
ip route add 192.168.0.0/16 via 172.30.0.2

# Start ifplugd
#/usr/sbin/ifplugd -a -i eth1 -q -f -u0 -d0 -I -r /root/project/eth1-updown
#./eth1-updown eth1 up
