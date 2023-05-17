# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import NanoService
import time


# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbackInit(NanoService):
    @ncs.application.NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info('Creating Lower-link...')

    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info('Deleted Lower-link is deleted.')


class ServiceCallbackReady(NanoService):
    @ncs.application.NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info('Lower-link plan is ready.')
        self.log.info(f'Sleeping {service.sleep} ms')
        time.sleep(service.sleep/1000)

    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info('Deleting Lower-link...')


class ServiceComponentVlanLinkCallbacks(NanoService):
    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Init state reached...')
        return


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')

        # Service callbacks require a registration for a 'service point',
        # as specified in the corresponding data model.
        #
        self.register_nano_service(servicepoint='lower-link-servicepoint', componenttype="ncs:self", state="ncs:init", nano_service_cls=ServiceCallbackInit)
        self.register_nano_service(servicepoint='lower-link-servicepoint', componenttype="ncs:self", state="ncs:ready", nano_service_cls=ServiceCallbackReady)
        self.register_nano_service(servicepoint='lower-link-servicepoint', componenttype="lower-link:vlan-link", state="ncs:init", nano_service_cls=ServiceComponentVlanLinkCallbacks)
        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
