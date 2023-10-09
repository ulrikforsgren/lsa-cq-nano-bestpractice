ifeq "$(NCS_DIR)" ""
$(error NCS_DIR is not setup. Source ncsrc to setup NSO environment before proceeding)
endif

CFS_PACKAGES =  $(wildcard ../package-store/cfs/*)
RFS_PACKAGES =  $(wildcard ../package-store/rfs/*)

NSO_VERSION = $(shell ncs --version)
NSO_VER_MAJ = $(shell echo $(NSO_VERSION) | cut -f1 -d.)
NSO_VER_MIN = $(shell echo $(NSO_VERSION) | cut -f2 -d. | cut -f1 -d_)
NSO_MAJOR_VERSION = $(NSO_VER_MAJ).$(NSO_VER_MIN)

ifeq (, $(shell which python))
 $(error python not found in PATH.)
endif

PYTHON_MAJOR_VERSION=$(shell python --version 2>&1 | cut -f2 -d' ' | cut -f1 -d\.)

ifeq "$(NSO_MAJOR_VERSION)" "5.2"
LSA_NED=tailf-nso-nc-$(NSO_MAJOR_VERSION)
  ifeq "$(PYTHON_MAJOR_VERSION)" "3"
    $(error pyang embedded with NSO version 5.2 requires Python 2.x to work. A simple solution is to patch $(NCS_DIR)/lib/pyang/bin/pyang to use python2 and comment this error message.)
  endif
else ifeq "$(NSO_MAJOR_VERSION)" "5.3"
LSA_NED=tailf-nso-nc-$(NSO_MAJOR_VERSION)
else
LSA_NED=cisco-nso-nc-$(NSO_MAJOR_VERSION)
RFS_NED_OPTIONS=--lsa-lower-nso $(LSA_NED)
endif



.PHONY: all
all:
	@echo "Current build: $(wildcard *-BUILD)"
	@echo "NSO major version: $(NSO_MAJOR_VERSION) ($(NSO_VERSION))"
	@echo
	@echo "Makefile rules:"
	@echo " * lsa           Setup an LSA NSO system with one CFS and two RFS nodes"
	@echo " * start         start environment"
	@echo " * stop          stop environment"
	@echo " * bash-<host>   start a bash shell in node/container <host>"
	@echo " * cli-<host>    start an NSO CLI in node/container <host>"
	@echo " * ncp-<device>  start a netsim-control-panel in the device container"

.PHONY: check-build
check-build:
	@if [ ! -e LSA-BUILD ]; then \
	  echo 'ERROR: You need to build before starting. Run "make lsa" to build.'; \
	  exit 1; \
        fi


.PHONY: lsa
lsa: LSA-BUILD upper-nso lower-nso-1 lower-nso-2

.PHONY: LSA-BUILD
LSA-BUILD:
	@touch LSA-BUILD

.PHONY: build-pkgs
build-pkgs: ../package-store/BUILT ../package-store/cfs/rfs-vlan-nc ../package-store/cfs/lower-link-nc ../package-store/cfs/$(LSA_NED)
../package-store/BUILT:
	for i in $(CFS_PACKAGES) $(RFS_PACKAGES); do \
	  $(MAKE) -C $${i}/src all || exit 1; \
	done
	touch ../package-store/BUILT

../package-store/cfs/$(LSA_NED):
	cp -rp ${NCS_DIR}/packages/lsa/$(LSA_NED) ../package-store/cfs/.

../package-store/cfs/rfs-vlan-nc:
	ncs-make-package --no-netsim --no-java --no-python \
		--lsa-netconf-ned ../package-store/rfs/rfs-vlan/src/yang \
		--lsa-lower-nso cisco-nso-nc-$(NSO_MAJOR_VERSION) \
		--package-version $(NSO_MAJOR_VERSION) --dest $@ $(@F)
	$(MAKE) -C $@/src

../package-store/cfs/lower-link-nc:
	ncs-make-package --no-netsim --no-java --no-python \
		--lsa-netconf-ned ../package-store/rfs/lower-link/src/yang \
		--lsa-lower-nso cisco-nso-nc-$(NSO_MAJOR_VERSION) \
		--package-version $(NSO_MAJOR_VERSION) --dest $@ $(@F)
	$(MAKE) -C $@/src


#
# LSA
#

upper-nso: build-pkgs
	cp -rp node-template $@

lower-nso-%: build-pkgs
	cp -rp node-template $@
	cp initial_data/devices-$@.xml $@/var/cdb/.

.PHONY: clean
clean:
	rm -rf upper-nso lower-nso-1 lower-nso-2
	rm -f LSA-BUILD
	rm -rf ../package-store/cfs/rfs-vlan-nc
	rm -rf ../package-store/cfs/lower-link-nc
	rm -rf ../package-store/cfs/$(LSA_NED)

.PHONY: clean-pkgs
clean-pkgs:
	for i in $(CFS_PACKAGES) $(RFS_PACKAGES); do \
	  $(MAKE) -C $${i}/src clean || exit 1; \
	done
	rm -f ../package-store/BUILT

.PHONY: start
start: check-build
	docker-compose up
	./initial_data/startup-lsa-docker-compose.sh


.PHONY: stop
stop:
	docker-compose down


#
# CLI
#

bash-%:
	docker-compose exec -it $(subst bash-,,$@) /bin/bash -c "cd /root/nso-project; /bin/bash"
cli-%:
	docker-compose exec -it $(subst cli-,,$@) /bin/bash -lc "cd /root/nso-project; ncs_cli -u admin -C"
ncp-%:
	docker-compose exec -it $(subst ncp-,,$@) /app/netsim-control-panel

