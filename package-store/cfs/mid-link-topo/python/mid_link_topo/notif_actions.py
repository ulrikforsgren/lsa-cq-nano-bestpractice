import ncs
from ncs.maapi import Maapi
from ncs.dp import Action
import re
import traceback

class NotifAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        self.log.info(f'path={input.path}')
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
        pass

class PlanNotificationAction(NotifAction):
    def do_action(self, t, input):
        try:
            root = ncs.maagic.get_root(t)
            rfs_name = kp_to_rfs_name(input.path)
            self.log.info(f'device_name={rfs_name}')
            notification = root._get_node(input.path)
            service_name = kp_to_service_name(notification.service)

            if str(notification) == 'plan-state-change':
                return self._handle_plan_state_change(root, 
                                                      service_name, 
                                                      notification)
            elif str(notification) == 'service-commit-queue-event':
                return self._handle_service_commit_queue_event(root, 
                                                               rfs_name, 
                                                               service_name, 
                                                               notification)
            else:
                self.log.info(f'Got unknown notification type {notification}')
                return True
            
        except Exception as e:
            self.log.error('ERROR: ', e)
            self.log.error(traceback.format_exc())
            return False
        
    def _handle_plan_state_change(self, root, service_name, notification):
        self.log.info(f'{notification}: {notification.operation}, {notification.component}, {notification.state}')
        ld = link_data(root, service_name)
        if notification.operation == 'deleted':
            if notification.state == 'init' and notification.component != 'self':
                ld.devices.create(notification.component).status = 'unprovisioned'
                return True
            
            self.log.info(f'Got unhandled notif: {notification}')
            
        return True
    
    def _handle_service_commit_queue_event(self, root, rfs_name, service_name, notification):
        self.log.info(f'Service {service_name} commit queue event, id: {notification.id} , status: {notification.status}')
        ld = link_data(root, service_name)

        for d in rfs_cq_item(root, rfs_name, notification.id).devices:
            ld_device = ld.devices.create(d)
            if ld_device.status == 'executing' and notification.status == 'waiting':
                continue


            ld_device.status = notification.status
        
        return True

class EventNotficationAction(NotifAction):
    def do_action(self, t, input):
        try:
            self.log.info('Got event notification')
            self.log.info(f'path={input.path}')
            root = ncs.maagic.get_root(t)
            rfs_name = kp_to_rfs_name(input.path)
            notification = root._get_node(input.path)
            if str(notification) == 'ncs-commit-queue-progress-event':
                self._handle_commit_queue_progress_event(root, rfs_name, notification)

            return True
        except Exception as e:
            self.log.error('ERROR', e)
            self.log.error(traceback.format_exc())
            return False
        
    def _handle_commit_queue_progress_event(self, root, rfs_name, notification):
        self.log.info(f'CQ Progress event: {notification.state}')
        if notification.state == 'executing':
            cq_item = rfs_cq_item(root, rfs_name, notification.id)
            if hasattr(cq_item, 'services'):
                service_kp = str()
                for s in cq_item.services:
                    service_kp = s
                self.log.info(f'Service kp: {service_kp}')
                ld = link_data(root, kp_to_service_name(service_kp))
                if hasattr(notification, 'transient_devices'):
                    for d in notification.transient_devices:
                        ld_device = ld.devices[d.name]
                        ld_device.status = notification.state
                        ld_device.transient_error = True
                        ld_device.when = notification._parent._parent.received_time
                        #ld_device.reason = TODO

                        if hasattr(ld_device, 'retries'):
                            ld_device.retries = ld_device.retries + 1
                        else:
                            ld_device.retries = 0
                else:
                    for d in cq_item.devices:
                        ld_device = ld.devices[d.name]
                        ld_device.status = notification.state
                        ld_device.transient_error = False
                        ld_device.when = notification._parent._parent.received_time
                        #ld_device.reason = TODO
                        ld_device.retries = 0

            else: # A completed CQ item has "completed-services" attribute
                self.log.info(f'Item {notification.id} is not in CQ anymore.')

        elif notification.state == 'failed':
            self.log.info('Handlig failed event cq notif')
            for s in notification.failed_services:
                service_name = kp_to_service_name(s.name)
                self.log.info(f'Failed service {service_name}')
                ld = link_data(root, service_name)

                if hasattr(s, 'completed_devices'):
                    for d in s.completed_devices:
                        self.log.info(f'Failed device {d}')
                        ld.devices[d].reason = notification.failed_devices[d].reason
                        ld_device.transient_error = True
                        ld_device.when = notification._parent._parent.received_time

        elif notification.state == 'completed':
            self.log.info('Handlig completed event cq notif')
            for s in notification.completed_services:
                service_name = kp_to_service_name(s.name)
                self.log.info(f'Completed service {service_name}')
                ld = link_data(root, service_name)

                if hasattr(s, 'completed_devices'):
                    for d in s.completed_devices:
                        self.log.info(f'Completed device {d}')
                        ld_device = ld.devices[d]
                        ld_device.status = 'completed'
                        ld_device.reason = ''
                        ld_device.transient_error = False
                        ld_device.when = notification._parent._parent.received_time
                        ld_device.retries = 0

def link_data(root, service_name):
    return root.ncs__services.mid_link_topo__mid_link_data[service_name]

#This assumes that the CFS and RFS service has the same name
def kp_to_service_name(service_kp):
    return re.search(r"('[^#]*')",service_kp).group().replace("'", "")

def kp_to_rfs_name(rfs_kp):
    return re.search(r'\{(.*?)\}', rfs_kp).group(1)

def rfs_cq_item(root, rfs, id):
    rfs_cq = root.ncs__devices.device[rfs].live_status.ncs__devices.commit_queue
    return rfs_cq.queue_item[id] if rfs_cq.queue_item.exists(id) else rfs_cq.completed.queue_item[id]