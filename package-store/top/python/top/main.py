# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service, PlanComponent
import resource_manager.id_allocator as id_allocator


# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbacks(Service):

    # The create() callback is invoked inside NCS FASTMAP and
    # must always exist.
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info('Service create(service=', service._path, ')')

        self_plan = self.init_plan(service)

        if service.vid:
            vid = service.vid
        elif service.allocate_rm_vid:
            # allocate vid
            vid = self.get_vid(tctx, root, service)
            if not vid:
                return
        elif service.use_resources_vid:
            vid = root.resources_top.vid
            if not vid:
                return
        else:
            raise Exception("No VLAN id has been set.")

        vars = ncs.template.Variables()
        vars.add('IFACE', 'eth0')
        vars.add('UNIT', '1')
        vars.add('VID', vid)
        template = ncs.template.Template(service)
        template.apply('top-direct-template', vars)
        template.apply('top-stacked-template', vars)

        self_plan.set_reached('ncs:ready')

    # The pre_modification() and post_modification() callbacks are optional,
    # and are invoked outside FASTMAP. pre_modification() is invoked before
    # create, update, or delete of the service, as indicated by the enum
    # ncs_service_operation op parameter. Conversely
    # post_modification() is invoked after create, update, or delete
    # of the service. These functions can be useful e.g. for
    # allocations that should be stored and existing also when the
    # service instance is removed.

    # @Service.pre_lock_create
    # def cb_pre_lock_create(self, tctx, root, service, proplist):
    #     self.log.info('Service plcreate(service=', service._path, ')')

    # @Service.pre_modification
    # def cb_pre_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')

    # @Service.post_modification
    # def cb_post_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service postmod(service=', kp, ')')

    def init_plan(self, service):
        """Create and initialize data-plan for 'self'.

        :param service: service parameters
        :type  service: ncs.maagic.ListElement
        :return: the plan for the service
        :rtype: PlanComponent
        """
        self.log.debug("init_plan(): Entering function")
        # Self PlanComponent
        self_plan = PlanComponent(service, 'self', 'ncs:self')
        self_plan.append_state('ncs:init')
        self_plan.append_state('ncs:ready')
        self_plan.set_reached('ncs:init')
        return self_plan


    def get_vid(self, tctx, root, service):
        """Get an index from the resource manager.

        :param tctx: Transaction context
        :type tctx:  _ncs.TransCtxRef
        :param root: Root node
        :type root:  ncs.maagic.Node
        :return:     the allocated index if the resource manager allocated one, else None
        :rtype:      int or None
        """
        self.log.debug("get_index(): Entering function")
        svc_xpath = "/%s[name='%s']" % (service, service.name)

        # To use if we dont want to use RFM in demo
        #index = random.randint(0,1048576)

        pool = 'vlan-pool'

        # requesting ID
        id_allocator.id_request(service,
                                svc_xpath,
                                tctx.username,
                                pool,
                                'top-%s' % service.name,
                                False,
                                redeploy_type='reactive-re-deploy')
        # getting ID if already allocated (else None)
        index = id_allocator.id_read(tctx.username, root,
                                     pool, 'top-%s' % service.name)
        return index


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
        self.register_service('top-servicepoint', ServiceCallbacks)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
