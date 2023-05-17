#!/bin/sh

lower_nso() {
    echo "Setting up lower-nso-$1..."
    ncs_cli --port $(expr 4571 + $1) -u admin 2> /dev/null <<EOF
config
set services plan-notifications subscription service-sub service-type /ncs:services/lower-link:lower-link component-type self
set ncs:devices device * trace pretty
commit
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
exit
EOF
}

mid_nso() {
    echo "Setting up mid-nso-$1..."
    n2=$(expr $1 \* 2)
    n1=$(expr $n2 - 1)
    port=4569
    ncs_cli --port $port -u admin <<EOF
config
set cluster device-notifications enabled
set cluster remote-node lower-nso-$n1 address 127.0.0.1 port $(expr 2024 + $n1) \
authgroup default username admin
set cluster remote-node lower-nso-$n2 address 127.0.0.1 port $(expr 2024 + $n2) \
authgroup default username admin
set cluster commit-queue enabled
commit
request cluster remote-node lower-nso-$n1 ssh fetch-host-keys
request cluster remote-node lower-nso-$n2 ssh fetch-host-keys
set devices global-settings commit-queue enabled-by-default true async atomic true error-option rollback-on-error retry-attempts 1 retry-timeout 1
set ncs:devices device lower-nso-$n1 device-type netconf ned-id $MNAME
set ncs:devices device lower-nso-$n1 authgroup default
set ncs:devices device lower-nso-$n1 lsa-remote-node lower-nso-$n1
set ncs:devices device lower-nso-$n1 state admin-state unlocked
set ncs:devices device lower-nso-$n2 device-type netconf ned-id $MNAME
set ncs:devices device lower-nso-$n2 authgroup default
set ncs:devices device lower-nso-$n2 lsa-remote-node lower-nso-$n2
set ncs:devices device lower-nso-$n2 state admin-state unlocked
set ncs:devices device lower-nso-$n1 netconf-notifications subscription three-layer-service-sub stream service-state-changes local-user admin
set ncs:devices device lower-nso-$n2 netconf-notifications subscription three-layer-service-sub stream service-state-changes local-user admin
set services plan-notifications subscription service-sub service-type /ncs:services/mid-link:mid-link component-type self
set ncs:devices device * trace pretty
commit
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
exit
EOF
}

set -e

for i in $(seq 1 4); do
    lower_nso $i;
done
mid_nso 1

