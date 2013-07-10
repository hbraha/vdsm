import logging
import os

import pyinotify

from netconf.iproute2 import Iproute2
from sourceRoute import DynamicSourceRoute
from vdsm.constants import P_VDSM_RUN


SOURCE_ROUTES_FOLDER = P_VDSM_RUN + 'sourceRoutes'
configurator = Iproute2()


class DHClientEventHandler(pyinotify.ProcessEvent):
    def process_IN_CLOSE_WRITE_filePath(self, sourceRouteFilePath):
        logging.debug("Responding to DHCP response in %s" %
                      sourceRouteFilePath)
        with open(sourceRouteFilePath, 'r') as sourceRouteFile:
            sourceRouteContents = sourceRouteFile.read().split()
            action = sourceRouteContents[0]
            device = sourceRouteContents[-1]
            sourceRoute = DynamicSourceRoute(device, configurator)

            if not sourceRoute.isVDSMInterface():
                logging.info("interface %s is not a libvirt interface" %
                             sourceRoute.device)
                return

            if action == 'configure':
                ip = sourceRouteContents[1]
                mask = sourceRouteContents[2]
                gateway = sourceRouteContents[3]
                sourceRoute.configure(ip, mask, gateway)
            else:
                sourceRoute.remove()

            DynamicSourceRoute.removeInterfaceTracking(device)

        os.remove(sourceRouteFilePath)

    def process_IN_CLOSE_WRITE(self, event):
        self.process_IN_CLOSE_WRITE_filePath(event.pathname)


def subscribeToInotifyLoop():
    logging.debug("sourceRouteThread.subscribeToInotifyLoop started")

    # Subscribe to pyinotify event
    watchManager = pyinotify.WatchManager()
    handler = DHClientEventHandler()
    notifier = pyinotify.Notifier(watchManager, handler)
    watchManager.add_watch(SOURCE_ROUTES_FOLDER, pyinotify.IN_CLOSE_WRITE)

    # Run once manually in case dhclient operated while supervdsm was down
    # Run sorted so that if multiple files exist for an interface, we'll
    # execute them alphabetically and thus according to their time stamp
    for filePath in sorted(os.listdir(SOURCE_ROUTES_FOLDER)):
        handler.process_IN_CLOSE_WRITE_filePath(
            SOURCE_ROUTES_FOLDER + '/' + filePath)

    notifier.loop()
