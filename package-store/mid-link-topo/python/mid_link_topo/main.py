# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.maapi import Maapi
from ncs.application import NanoService
from ncs.dp import Action
import time


class CreateKickers(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info("Creating notification-kicker for create...")
        notif_kicker = root.kicker__kickers.ncs_kicker__notification_kicker.create(f"{service.name}-create-notif-kicker")
        notif_kicker.action_name = "notify"
        notif_kicker.kick_node = "/mid-link-topo:actions"
        notif_kicker.selector_expr = "$SUBSCRIPTION_NAME='three-layer-service-sub' and service=$NAME and operation='modified' and status='reached' and state='ready' and component='self'"
        notif_var = notif_kicker.variable.create("NAME")
        notif_var.value = f"\"/ncs:services/lower-link:lower-link[lower-link:name='{service.name}']\""

        self.log.info("Creating notification-kicker for delete...")
        delete_notif_kicker = root.kicker__kickers.ncs_kicker__notification_kicker.create(f"{service.name}-delete-notif-kicker")
        delete_notif_kicker.action_name = "notify"
        delete_notif_kicker.kick_node = "/mid-link-topo:actions"
        delete_notif_kicker.selector_expr = "$SUBSCRIPTION_NAME='three-layer-service-sub' and service=$NAME and operation='deleted' and state='init' and component='self'"
        delete_notif_var = delete_notif_kicker.variable.create("NAME")
        delete_notif_var.value = f"\"/ncs:services/lower-link:lower-link[lower-link:name='{service.name}']\""


class MidLinkNanoServiceCallbacks(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Mid Link Nano service CB: {service.name} - {component} - {state} ')
        #for rfs in service.rfs_node:
        #    self.log.info(f"Creating service for RFS='{rfs.name}'")
        #    rfs_device = root.ncs__devices.device[rfs.name]
        #    link = rfs_device.config.services.lower_link.create(service.name)
        #    for device in rfs.devices:
        #        link_device = link.devices.create(device.name)
        #        link_device.list_entries = device.list_entries

        #    link.vid = service.vid
        #    link.unit = service.unit
        #    link.iface = service.iface
        #    link.sleep = rfs.sleep
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


class NotificationAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        if hasattr(Maapi, "run_with_retry"):
            def wrapped_do_action(trans):
                return self.do_action(trans, input)
            with ncs.maapi.Maapi() as m:
                with ncs.maapi.Session(m, 'admin', 'system'):
                    m.run_with_retry(wrapped_do_action)
        else:
            with ncs.maapi.single_write_trans('admin', 'system') as t:
                self.do_action(t, input)
                t.apply()

    def do_action(self, t, input):
        try:
            import re
            root = ncs.maagic.get_root(t)
            self.log.info(f'path={input.path}')
            device_name = re.search(r'\{(.*?)\}', input.path).group(1)
            self.log.info(f'device_name={device_name}')
            notification = root._get_node(input.path)
            # TODO: Optimal?
            service_name = re.search(r"('[^#]*')", notification.service).group().replace("'", "")
            if notification.operation == 'modified':
                self.log.info(f"Adding mid link data for '{service_name}'...")
                link_data = root.ncs__services.mid_link_topo__mid_link_data.create(service_name)
                link_data_device = link_data.rfs_node.create(device_name)
                link_data_device.ready = True
            elif notification.operation == 'deleted':
                self.log.info(f"Removing mid link data for '{service_name}'...")
                del root.ncs__services.mid_link_topo__mid_link_data[service_name].rfs_node[device_name]
            params = t.get_params()
            params.dry_run_native()
            return True
        except Exception as e:
            return False


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
        self.register_nano_service(servicepoint='mid-link-topo-servicepoint',
                                   componenttype="mid-link-topo:vlan-link", state="ncs:init", nano_service_cls=CreateKickers)
        self.register_nano_service(servicepoint='mid-link-topo-servicepoint',
                                   componenttype="mid-link-topo:vlan-link",
                                   state="mid-link-topo:add-rfs-config", nano_service_cls=MidLinkNanoServiceCallbacks)

        self.register_nano_service(servicepoint='mid-link-topo-servicepoint', componenttype="ncs:self", state="ncs:init", nano_service_cls=NanoServiceCallbackInit)
        self.register_nano_service(servicepoint='mid-link-topo-servicepoint', componenttype="ncs:self", state="ncs:ready", nano_service_cls=NanoServiceCallbackReady)

        self.register_action('mid-link-topo-notify', NotificationAction)
        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
