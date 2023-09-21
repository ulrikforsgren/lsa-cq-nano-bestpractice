# Delete default route to avoid interference when interface goes up/down
ip route del default
ip route add 172.30.0.0/24 via 192.168.0.2

# Start ifplugd
#/usr/sbin/ifplugd -a -i eth0 -q -f -u0 -d0 -I -r `pwd`/eth0-updown
#./eth0-updown eth0 up
