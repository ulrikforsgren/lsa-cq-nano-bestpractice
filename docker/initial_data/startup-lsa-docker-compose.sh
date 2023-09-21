#!/bin/sh

set -e

source .env

NSO_VERSION=`echo $NSO_VERSION | cut -f1 -d_ | cut -f1 -d-`
NSO_VER_MAJ=`echo $NSO_VERSION | cut -f1 -d.`
NSO_VER_MIN=`echo $NSO_VERSION | cut -f2 -d.`
NSO_MAJOR_VERSION=$NSO_VER_MAJ.$NSO_VER_MIN

if [ "$NSO_MAJOR_VERSION" = "5.2" ]; then
  NEDID=lsa-netconf
  LSA_NEDID=tailf-nso-nc-$NSO_MAJOR_VERSION
elif [ "$NSO_MAJOR_VERSION" = "5.3" ]; then
  NEDID=lsa-netconf
  LSA_NEDID=tailf-nso-nc-$NSO_MAJOR_VERSION
else
  NEDID=cisco-nso-nc-$NSO_MAJOR_VERSION
fi


echo "Initialize NSO nodes:"

echo "On lower-nso-1: fetch ssh keys from devices"
echo "On lower-nso-1: perform sync-from"
docker-compose exec -T lower-nso-1 bash -l -c "ncs_cli -u admin" <<EOF
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
EOF
docker-compose exec -T lower-nso-1 bash -l -c "ncs_cli -u admin" <<EOF
config
set services plan-notifications subscription service-sub service-type /ncs:services/lower-link:lower-link component-type self
commit
EOF

echo "On lower-nso-2: fetch ssh keys from devices"
echo "On lower-nso-2: perform sync-from"
docker-compose exec -T lower-nso-2 bash -l -c "ncs_cli -u admin" <<EOF
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
EOF
docker-compose exec -T lower-nso-2 bash -l -c "ncs_cli -u admin" <<EOF
config
set services plan-notifications subscription service-sub service-type /ncs:services/lower-link:lower-link component-type self
commit
EOF

## Must sync-from nso-upper last, since their sync-froms
## change their CDB

echo "On upper-nso: configure cluster remote nodes: lower-nso-1 and lower-nso-2"
echo "On upper-nso: enable cluster device-notifications and cluster commit-queue"
echo "On upper-nso: fetch ssh keys from cluster remote nodes"
echo "On upper-nso: fetch ssh keys from devices"
echo "On upper-nso: perform sync-from"

docker-compose exec -T upper-nso bash -l -c "ncs_cli -u admin" <<EOF
config
set cluster authgroup default default-map remote-name admin remote-password admin
set cluster device-notifications enabled
set cluster remote-node lower-nso-1 address 172.30.0.4 port 2022 authgroup default username admin
set cluster remote-node lower-nso-2 address 172.30.0.5 port 2022 authgroup default username admin
set cluster commit-queue enabled
commit
request cluster remote-node lower-nso-1 ssh fetch-host-keys
request cluster remote-node lower-nso-2 ssh fetch-host-keys
exit
EOF
docker-compose exec -T upper-nso bash -l -c "ncs_cli -u admin" <<EOF
config
set ncs:devices device lower-nso-1 device-type netconf ned-id $NEDID
set ncs:devices device lower-nso-1 authgroup default
set ncs:devices device lower-nso-1 lsa-remote-node lower-nso-1
set ncs:devices device lower-nso-1 state admin-state unlocked
set ncs:devices device lower-nso-1 out-of-sync-commit-behaviour accept
set ncs:devices device lower-nso-2 device-type netconf ned-id $NEDID
set ncs:devices device lower-nso-2 authgroup default
set ncs:devices device lower-nso-2 lsa-remote-node lower-nso-2
set ncs:devices device lower-nso-2 state admin-state unlocked
set ncs:devices device lower-nso-2 out-of-sync-commit-behaviour accept
commit
exit
EOF
docker-compose exec -T upper-nso bash -l -c "ncs_cli -u admin" <<EOF
config
set ncs:devices device lower-nso-1 netconf-notifications subscription three-layer-service-sub stream service-state-changes local-user admin
set ncs:devices device lower-nso-2 netconf-notifications subscription three-layer-service-sub stream service-state-changes local-user admin
set services plan-notifications subscription service-sub service-type /ncs:services/mid-link:mid-link component-type self
commit
set top:rfs-devices device ex0 lower-node lower-nso-1
set top:rfs-devices device ex1 lower-node lower-nso-1
set top:rfs-devices device ex2 lower-node lower-nso-1
set top:rfs-devices device ex3 lower-node lower-nso-2
set top:rfs-devices device ex4 lower-node lower-nso-2
set top:rfs-devices device ex5 lower-node lower-nso-2
commit
exit
EOF
docker-compose exec -T upper-nso bash -l -c "ncs_cli -u admin" <<EOF
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
exit
EOF
