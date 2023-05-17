NODES := lower-nso-1 lower-nso-2 lower-nso-3 lower-nso-4 \
		 mid-nso-1

NCSVER := $(shell ncs --version | sed 's/\([0-9]*\.[0-9]*\).*/\1/')
MNAME := cisco-nso-nc-$(NCSVER)

# all: lower-nso-1 lower-nso-2 lower-nso-3 lower-nso-4 netsim mid-nso-1
all: $(NODES) netsim
.PHONY: all

package-store/mid-link:
	$(MAKE) -C $@/src
.PHONY: package-store/mid-link

package-store/lower-link:
	$(MAKE) -C $@/src
.PHONY: package-store/lower-link

package-store/router:
	$(MAKE) -C $@/src
.PHONY: package-store/router

mid-nso-%: package-store/mid-link
	rm -rf $@
	ncs-setup --no-netsim --dest $@
	cp nso-etc/$@/ncs.conf $@
	ln -sf $(NCS_DIR)/packages/lsa/$(MNAME) $@/packages
	ln -sf ../../package-store/mid-link $@/packages
	$(MAKE) $@/packages/lower-link-nc-$(NCSVER)

mid-nso-1/packages/lower-link-nc-%:
	ncs-make-package --no-netsim --no-java --no-python \
		--lsa-netconf-ned package-store/lower-link/src/yang \
		--lsa-lower-nso cisco-nso-nc-$* \
		--package-version $* --dest $@ --build $(@F)

mid-nso-1/packages/lower-link-nc-%:
	ncs-make-package --no-netsim --no-java --no-python \
		--lsa-netconf-ned package-store/lower-link/src/yang \
		--lsa-lower-nso cisco-nso-nc-$* \
		--package-version $* --dest $@ --build $(@F)

mid-nso-2/packages/lower-link-nc-%:
	ncs-make-package --no-netsim --no-java --no-python \
		--lsa-netconf-ned package-store/lower-link/src/yang \
		--lsa-lower-nso cisco-nso-nc-$* \
		--package-version $* --dest $@ --build $(@F)

mid-nso-2/packages/lower-link-nc-%:
	ncs-make-package --no-netsim --no-java --no-python \
		--lsa-netconf-ned package-store/lower-link/src/yang \
		--lsa-lower-nso cisco-nso-nc-$* \
		--package-version $* --dest $@ --build $(@F)

lower-nso-%: package-store/lower-link package-store/router
	ncs-setup --no-netsim --dest $@
	cp nso-etc/$@/ncs-cdb/devs.xml $@/ncs-cdb
	cp nso-etc/$@/ncs.conf $@
	ln -sf ../../package-store/lower-link $@/packages
	ln -sf ../../package-store/router $@/packages

netsim:
	ncs-netsim create-network package-store/router 8 ex --dir ./netsim

start: stop
	ncs-netsim -a start
	cd mid-nso-1;    NCS_IPC_PORT=4569 sname=mid-nso-1   ncs -c ncs.conf
	cd lower-nso-1;  NCS_IPC_PORT=4572 sname=lower-nso-1 ncs -c ncs.conf
	cd lower-nso-2;  NCS_IPC_PORT=4573 sname=lower-nso-2 ncs -c ncs.conf
	cd lower-nso-3;  NCS_IPC_PORT=4574 sname=lower-nso-3 ncs -c ncs.conf
	cd lower-nso-4;  NCS_IPC_PORT=4575 sname=lower-nso-4 ncs -c ncs.conf
	MNAME=$(MNAME) ./init-all.sh

stop:
	ncs-netsim stop || true
	NCS_IPC_PORT=4569 ncs --stop || true
	NCS_IPC_PORT=4572 ncs --stop || true
	NCS_IPC_PORT=4573 ncs --stop || true
	NCS_IPC_PORT=4574 ncs --stop || true
	NCS_IPC_PORT=4575 ncs --stop || true

cli-mid-1:
	NCS_IPC_PORT=4569 ncs_cli -uadmin
cli-lower-1:
	NCS_IPC_PORT=4572 ncs_cli -uadmin
cli-lower-2:
	NCS_IPC_PORT=4573 ncs_cli -uadmin
cli-lower-3:
	NCS_IPC_PORT=4574 ncs_cli -uadmin
cli-lower-4:
	NCS_IPC_PORT=4575 ncs_cli -uadmin

clean:
	make -C package-store/mid-link/src clean
	make -C package-store/lower-link/src clean
	make -C package-store/router/src clean
	rm -rf mid-nso-* lower-nso-* netsim
