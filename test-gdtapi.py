#!/usr/bin/env python3
''' ----------------------  ----------- #
# Author : samikang
# Date   : 24/10/2015
# Email  : xiangxiangster@hotmail.com
# ------------------------------------------------------------ '''

import unittest
import gdtapi
import logging
import sys
import time

formatter = logging.Formatter(fmt='%(levelname)s(%(module)s): %(asctime)s| %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

class GdtApiTestCase(unittest.TestCase):
    def setUp(self):
        self._api = gdtapi.GdtApi(host='192.168.1.1')
        self._api.configure(ipaddr='192.168.1.2', intf='eth2', log=logger)

   
    def test_set_value(self):
        self.assertEqual(self._api.set_value(
            'InternetGatewayDevice.Time.Enable.control', True), 0)
   
    def test_get_value_uptime(self):
        print(self._api.get_value('InternetGatewayDevice.DeviceInfo.UpTime'))

   
    def test_get_value_process(self):
        print(self._api.get_value('InternetGatewayDevice.DeviceInfo.ProcessStatus.CPUUsage'))


    @unittest.skip
    def test_get_value(self):
        self.assertEqual(self._api.get_value('InternetGatewayDevice.Time.Enable.control'), True)
if __name__ == '__main__':
    unittest.main()

