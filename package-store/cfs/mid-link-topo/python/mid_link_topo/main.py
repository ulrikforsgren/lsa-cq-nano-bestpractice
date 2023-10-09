# -*- mode: python; python-indent: 4 -*-
import ncs
import _ncs
from ncs.application import NanoService, Service
import time
from .notif_actions import PlanNotificationAction, EventNotficationAction

class MidLinkServiceCallbacks(Service):
    @Service.pre_modification
    def cb_pre_modification(self, tctx, op, kp, root, proplist):
        if op == _ncs.dp.NCS_SERVICE_CREATE:
            service_name = self.kp_to_svc_name(kp)
            self.log.debug(f'Creating mid-link-data {service_name}')
            root.ncs__services.mid_link_topo__mid_link_data.create(service_name)

    @Service.post_modification
    def cb_post_modification(self, tctx, op, kp, root, proplist):
        if op == _ncs.dp.NCS_SERVICE_DELETE:
            service_name = self.kp_to_svc_name(kp)
            link_data = root.ncs__services.mid_link_topo__mid_link_data[service_name]
            all_unprovisioned = True
            for d in link_data.devices:
                if d.status != 'unprovisioned':
                    all_unprovisioned = False
            
            if all_unprovisioned:
                self.log.debug(f'Removing mid-link-data {service_name}')
                del root.ncs__services.mid_link_topo__mid_link_data[service_name]

    def kp_to_svc_name(self, kp):
        return str(kp).split('{')[1].split('}')[0]
    
class CreateKickers(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        vars = ncs.template.Variables()
        vars.add('SERVICE_NAME', service.name)
        template = ncs.template.Template(service)
        template.apply('plan-notif-kicker-create', vars)
        template.apply('plan-notif-kicker-delete', vars)
        template.apply('service-commit-queue-event-notif-kicker', vars)
        template.apply('event-notif-kicker', vars)

class MidLinkNanoServiceCallbacks(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Mid Link Nano service CB: {service.name} - {component} - {state} ')

        for d in service.device:
            self.log.info(f'd={d.name}')
            rfsname = root.top__rfs_devices.device[d.name].lower_node
            self.log.info(f"Creating service for RFS='{rfsname}'")
            rfs_device = root.ncs__devices.device[rfsname]
            link = rfs_device.config.services.lower_link.create(service.name)
            link_device = link.devices.create(d.name)
            link_device.list_entries = d.list_entries
            link.vid = service.vid
            link.unit = service.unit
            link.iface = service.iface
            link.sleep = d.sleep
        self.log.info(f'Service created')


class NanoServiceCallbackInit(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Creating Mid-link...')

    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Mid-link is deleted.')


class NanoServiceCallbackReady(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Sleeping {service.sleep} ms')
        time.sleep(service.sleep/1000)
        self.log.info('Mid-link plan is ready.')

    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Deleting Mid-link...')

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
        self.register_service('mid-link-topo-servicepoint', MidLinkServiceCallbacks) 
        self.register_nano_service(servicepoint='mid-link-topo-servicepoint',
                                   componenttype="mid-link-topo:vlan-link", state="ncs:init", nano_service_cls=CreateKickers)
        self.register_nano_service(servicepoint='mid-link-topo-servicepoint',
                                   componenttype="mid-link-topo:vlan-link",
                                   state="mid-link-topo:add-rfs-config", nano_service_cls=MidLinkNanoServiceCallbacks)

        self.register_nano_service(servicepoint='mid-link-topo-servicepoint', componenttype="ncs:self", state="ncs:init", nano_service_cls=NanoServiceCallbackInit)
        self.register_nano_service(servicepoint='mid-link-topo-servicepoint', componenttype="ncs:self", state="ncs:ready", nano_service_cls=NanoServiceCallbackReady)

        self.register_action('mid-link-topo-notify', PlanNotificationAction)
        self.register_action('mid-link-topo-event-notify', EventNotficationAction)
        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
