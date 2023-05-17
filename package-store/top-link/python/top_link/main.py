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
        notif_kicker.kick_node = "/actions"
        notif_kicker.selector_expr = "$SUBSCRIPTION_NAME='three-layer-service-sub' and service=$NAME and operation='modified' and status='reached' and state='ready' and component='self'"
        notif_var = notif_kicker.variable.create("NAME")
        notif_var.value = f"\"/ncs:services/mid-link:mid-link[mid-link:name='{service.name}']\""

        self.log.info("Creating notification-kicker for delete...")
        delete_notif_kicker = root.kicker__kickers.ncs_kicker__notification_kicker.create(f"{service.name}-delete-notif-kicker")
        delete_notif_kicker.action_name = "notify"
        delete_notif_kicker.kick_node = "/actions"
        delete_notif_kicker.selector_expr = "$SUBSCRIPTION_NAME='three-layer-service-sub' and service=$NAME and operation='deleted' and state='init' and component='self'"
        delete_notif_var = delete_notif_kicker.variable.create("NAME")
        delete_notif_var.value = f"\"/ncs:services/mid-link:mid-link[mid-link:name='{service.name}']\""


class TopLinkNanoServiceCallbacks(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        for cfs in service.cfs_node:
            self.log.info(f'Creating service for CFS={cfs.name}')
            cfs_device = root.ncs__devices.device[cfs.name]
            mid_link = cfs_device.config.services.mid_link.create(service.name)
            mid_link.vid = service.vid
            mid_link.unit = service.unit
            mid_link.iface = service.iface
            mid_link.sleep = cfs.sleep
            for rfs in cfs.rfs_node:
                rfs_device = mid_link.rfs_node.create(rfs.name)
                rfs_device.sleep = rfs.sleep
                for device in rfs.devices:
                    link_device = rfs_device.devices.create(device.name)
                    link_device.list_entries = device.list_entries
        self.log.info(f'DONE')


class NanoServiceCallbackInit(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info('Creating Top-link...')

    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info("Top-link is deleted.")


class NanoServiceCallbackReady(NanoService):
    @NanoService.create
    def cb_nano_create(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info(f'Sleeping {service.sleep} ms')
        time.sleep(service.sleep/1000)
        self.log.info('Top-link plan is ready.')

    @NanoService.delete
    def cb_nano_delete(self, tctx, root, service, plan, component, state, proplist, compproplist):
        self.log.info("Deleting Top-link...")


class NotificationAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        if hasattr(Maapi, "run_with_retry"):
            def wrapped_do_action(trans):
                return self.do_action(trans, input)
            with ncs.maapi.Maapi() as m:
                with ncs.maapi.Session(m, 'admin', 'test_context'):
                    m.run_with_retry(wrapped_do_action)
        else:
            with ncs.maapi.single_write_trans('admin', 'test_context') as t:
                self.do_action(t, input)
                t.apply()

    def do_action(self, t, input):
        try:
            import re
            root = ncs.maagic.get_root(t)
            device_name = re.search(r'\{(.*?)\}', input.path).group(1)
            notification = root._get_node(input.path)
            service_name = re.search(r"('[^#]*')", notification.service).group().replace("'", "")
            if notification.operation == 'modified':
                self.log.info(f"Adding top link data for '{service_name}'...")
                link_data = root.ncs__services.top_link_data.create(service_name)
                link_data_device = link_data.cfs_node.create(device_name)
                link_data_device.ready = True
            elif notification.operation == 'deleted':
                self.log.info(f"Removing top link data for '{service_name}'...")
                self.log.info(f"State = {notification.state}")
                del root.services.top_link_data[service_name].cfs_node[device_name]
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

        self.register_nano_service(servicepoint='top-link-servicepoint', componenttype="top-link:cfs", state="ncs:init", nano_service_cls=CreateKickers)
        self.register_nano_service(servicepoint='top-link-servicepoint', componenttype="top-link:cfs", state="top-link:add-cfs-config", nano_service_cls=TopLinkNanoServiceCallbacks)

        self.register_nano_service(servicepoint='top-link-servicepoint', componenttype="ncs:self", state="ncs:init", nano_service_cls=NanoServiceCallbackInit)
        self.register_nano_service(servicepoint='top-link-servicepoint', componenttype="ncs:self", state="ncs:ready", nano_service_cls=NanoServiceCallbackReady)
        self.register_action('notify', NotificationAction)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
