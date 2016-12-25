#!/usr/bin/env python3

''' ----------------------  ----------- #
# Author : samikang
# Date   : 24/10/2015
# Email  : xiangxiangster@hotmail.com
# ------------------------------------------------------------ '''

import socket
import sys
import os
import google.protobuf.message
import pickle

cur_path = os.path.dirname(os.path.realpath(__file__))

if cur_path not in sys.path:
    sys.path.append(cur_path)

import gateway_debug_tool_protocol_pb2
import protobuf_to_dict

PROB_TYPE_DICT = {
    'unknownValue': gateway_debug_tool_protocol_pb2.Value.Unknown,
    'textValue': gateway_debug_tool_protocol_pb2.Value.Text,
    'boolValue': gateway_debug_tool_protocol_pb2.Value.Bool,
    'intervalValue': gateway_debug_tool_protocol_pb2.Value.Interval,
    'enumValue': gateway_debug_tool_protocol_pb2.Value.Enum,
    'uIntervalValue': gateway_debug_tool_protocol_pb2.Value.UInterval,
    'llIntervalValue': gateway_debug_tool_protocol_pb2.Value.LLInterval,
    'iPv4Value': gateway_debug_tool_protocol_pb2.Value.IPv4,
    'iPv6Value': gateway_debug_tool_protocol_pb2.Value.IPv6
}

proto_list = [
    'unknownValue', 'boolValue', 'textValue',
    'intervalValue', 'enumValue', 'uIntervalValue',
    'ullIntervalValue', 'udidValueValue', 'llIntervalValue',
    'sIntervalValue', 'usIntervalValue', 'iPv4Value',
    'eui48Value', 'iPv6Value', 'multiValue',
    'dIntervalValue', 'container', 'addToContainer',
    'removeFromContainer', 'timeValValue'
]
proto_enum = {}

for i in range(1, len(proto_list) + 1):
    proto_enum[i] = proto_list[i - 1]

BUFFER_LEN = 1024
DELAY = 2

class GdtApi(object):
    """
    The APIs to manipulate with DUT via the protobuf
    that is used by the gateway debug tool
    """

    def __init__(self, host=None, port=9998, timeout=5, **kwargs):
        """
        Initialize a GDT API client.
        
        Params:
            host:
                The address of the GDT server.
            port:
                The port of the GDT server.
            timeout:
                The timeout to wait for the response.

        Optional params:
            log: 
                The logger to output the log information.
            intf: 
                The network interface to be used. This is only supported
                under linux system.
            ipaddr:
                The ip address to be used. This is only supported under
                linux system.            
        """
        
        super().__init__(host, **kwargs)
        
        self._msg = gateway_debug_tool_protocol_pb2.ServerMessage()
        self._msg_recv = gateway_debug_tool_protocol_pb2.ClientMessage()
        self._msg.connect.ids.append('')
        self._opts['port'] = port
        self._opts['timeout'] = timeout

    def _connect_get_info(self): 
        """
        connect to DUT, and get the whole data from DUT.
        Return:
        The dictionary of the json object if successful.
        -1 if fail.
        
        """
        
        self.config_intf()        

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._opts['timeout'])
            s.connect((self._opts['host'], self._opts['port']))
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self.logerror(e)
            s.close()
            return -1

        #send connection request
        data_bytes = self._msg.SerializeToString()

        try:
            s.sendall('{} '.format(len(data_bytes)).encode() + data_bytes)
        except socket.timeout as e:
            self.logerror(e)
            s.close()
            return -1

        #read the length of received data
        header = str(s.recv(7))
        idx = header.find(' ') 
        returnsize = int(header[2:idx])
        self.logdebug('The size of response is {}'.format(returnsize))

        #read all of received data
        blocknum = int(returnsize / BUFFER_LEN)
        self.logdebug('The number of blocks is {}'.format(blocknum))
        remain = returnsize % BUFFER_LEN
        self.logdebug('The remaining data length after all the blocks is {}'.format(remain))
        
        finalstring = b''

        for i in range(0, blocknum):
            data=s.recv(BUFFER_LEN)
            self.delay(DELAY, 'No')
            finalstring += data

        self.delay(DELAY, 'No')

        data=s.recv(remain)
        finalstring += data

        s.close()

        #Parse the Protobuf string
        try:
            state_parse = self._msg_recv.ParseFromString(finalstring)
        except google.protobuf.message.DecodeError as e:
            self.loginfo(e)
            return -1
            
        if state_parse is None:
            self.logdebug('The string can be parsed successfully.')
        else:
            self.logfail('The string cannot be parsed.')
            return -1
        
        #convert the Protobuf string to dict
        return protobuf_to_dict.protobuf_to_dict(self._msg_recv.valueChanged)

    def _dump_vs(self, vs):
        """
        Dump the value store to a file for future reuse.
        Return:
            0 if successful.
            -1 if fail.    
        """
        
        vs_file = 'vs_{}.pickle'.format(self._opts.get('intf'))
        self.logdebug('Dump value store to {}'.format(vs_file))
        try:
            with open(vs_file, 'wb') as f:
                pickle.dump(vs, f)
            return 0
        except FileNotFoundError as e:
            self.logerror(e)
            return -1   
        except PermissionError as e:
            return -1

    def _remove_vs(self):
        """
        Remove the value store file.
        Return:
            0 if successful.
            -1 if fail.
        """
        
        vs_file = 'vs_{}.pickle'.format(self._opts.get('intf'))
        self.logdebug('Remove the value store file {}'.format(vs_file))
        try:
            os.remove(vs_file)
            return 0
        except OSError as e:
            self.logerror(e) 
            return -1  

    def _load_vs(self):
        """
        Read the value store from the file
        Return:
            the value store if successful.
            -1 if fail.        
        """
        
        vs_file = 'vs_{}.pickle'.format(self._opts.get('intf'))
        self.logdebug('Load value store from {}'.format(vs_file))
        try:
            with open(vs_file, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError as e:
            self.logdebug(e)
            return -1
        except EOFError:
            return -1

    def _get_and_search_item(self, param, enforce=True):
        """
        retrieve all the parameters and search for the
        expected item
        Return:
        the item if found.
        -1 if fail
        """
        
        # try to load from value store file first.
        if enforce:
            resp = self._connect_get_info()
            connect = True
        else:
            resp = self._load_vs()
            connect = False
            if resp == -1:
                # try to read from the dut
                resp = self._connect_get_info()
                connect = True
        if resp == -1:
            self.logfail('The response is invalid.')
            return -1
        
        try:
            items = resp['value']
        except KeyError:
            self.logfail('The key value is not found in response.')
            self._remove_vs()
            return -1

        for item in items:
            if item['id'] == param:
                if connect:
                    self._dump_vs(resp)
                return item
        
        self._remove_vs()
        self.logfail('The item {} is not found in the response.'.format(param))
        return -1
        

    def get_value(self,param): 
        """
        get the parameter to the value via protobuf.
        
        Params:
            param:
                The parameter to get the value.

        return value
            The value of the parameter if successful.
            -1 if fail         
        """
  
        item = self._get_and_search_item(param)
        
        if item == -1:
            return -1

        protobuftype = proto_enum[item['type']]
        if protobuftype in item:
            val = item[protobuftype]['value']
        else:
            val = item['unknownValue']['value']     
        self.loginfo('the value of {} is {}'.format(param, val))             
        return val
   
    def set_value(self, param, value, check=False):
        """
        Set the parameter to the value via protobuf.
        
        Params:
            param:
                The parameter to set the value.
            value:
                The value to be set.
            check:
                Whether do a check by using get again or not.
        Return:
            0: successful.
            -1: fail.
        
        """
        
        # check the length of the valueEdited first.
        # if there are already value, delete them first.
        
        valueEdited = self._msg.valueEdited.value
        if len(valueEdited) > 0:
            del valueEdited[0:len(valueEdited)]

        param_type = self.get_param_type(param)
        if param_type == -1:
            return -1
        
        rtn = GdtApi.validate_value(value, param_type)
        if rtn == -1:
            self.logfail('The value {} is not valid for type '
                          '{}'.format(value, param_type))
            return -1
            
        new_val_elem = valueEdited.add()
        new_val_elem.id = param
        new_val_elem.type = PROB_TYPE_DICT[param_type]

        rtn = GdtApi.set_elem_value(new_val_elem, param_type, value)
        if rtn == -1:
            valueEdited.remove(new_val_elem)
            return -1
        
        self.config_intf()
            
        # now create the socket and send the message.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((self._opts['host'], self._opts['port']))
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self.logerror(e)
            s.close()
            return -1
        self.logdebug('new_val_elem  is: {}'.format(new_val_elem))                 
        data_bytes = self._msg.SerializeToString()
        self.logdebug('data_bytes  is: {}'.format(data_bytes)) 
    
        try:
            s.sendall('{} '.format(len(data_bytes)).encode() + data_bytes)
        except socket.timeout as e:
            self.logerror(e)
            s.close()
            return -1
        
        s.close() 
        
        if check:
            self.delay(DELAY, 'No')
            expect_value=self.get_value(param)
            if expect_value == value:
                self.logpass('The value of {} is updated successfully.'.format(param))
                return 0
            else:   
                self.logfail('The value of {} is not updated.'.format(value))
                return -1
        else:
            self.logpass('The value of {} is updated successfully.'.format(param))
            return 0
                    
    @staticmethod
    def set_elem_value(elem, param_type, value):
        """
        Set the corresponding value field in element according to 
        different types.
        
        Params:
            elem:
                The element object to set the value.
            param_type:
                The type of the parameter.
            value:
                The value to be set.
        Return:
            0: successful.
            -1: fail
        
        """
        
        if param_type == 'textValue':
            elem.textValue.value = value
        elif param_type == 'boolValue':
            elem.boolValue.value = value
        elif param_type == 'intervalValue':
            elem.intervalValue.value = int(value)
        elif param_type == 'enumValue':
            elem.enumValue.value = int(value)
        elif param_type == 'uIntervalValue':
            elem.uIntervalValue.value = int(value)
        elif param_type == 'llIntervalValue':
            elem.llIntervalValue.value = int(value)
        elif param_type == 'ipv4Value':
            elem.ipv4Value.value = value
        elif param_type == 'ipv6Value':
            elem.ipv6Value.value = value
        elif param_type == 'unknownValue':
            elem.unknownValue.value = value
        else:
            self.logfail('The type {} is not supported.'.format(param_type))
            return -1
        return 0    
        
    @staticmethod    
    def validate_value(value, param_type):
        """
        Validate whether the value to be set is in the correct type.
        
        Params:
            value:
                The value to be set.
            param_type:
                The type of the parameter to be set.
        Return:
            0: The value matches the type.
            -1: The value is not the same as the valid value of type.
        """
        if (param_type == 'textValue'  
           or param_type == 'iPv4Value'  
           or param_type == 'iPv6Value'):
            if isinstance(value, str):
                return 0
            else:
                return -1
        elif param_type == 'boolValue':
            if isinstance(value, bool):
                return 0
            else:
                return -1
        elif param_type == 'unknownValue':
            return 0
        elif (param_type == 'intervalValue' or param_type == 'uIntervalValue'
            or param_type == 'llIntervalValue' or param_type == 'enumValue'):
            if isinstance(value, int):
                return 0
            else:
                return -1             
        else:
            self.logfail('The type {} is not supported.'.format(param_type))
            return -1
                
    def get_param_type(self, param):
        """
        Get the type of the parameter from the profile.
        
        Params:
            param:
                The parameter in the value store
        Return:
            The type of the parameter if it is found in the profile.
            -1 if fail
        """   

        item = self._get_and_search_item(param, enforce=False)
        
        if item == -1:
            return -1
        
        proto_buf_type = proto_enum[item['type']]
        self.logdebug('The type of {} is: {}'.format(param, proto_buf_type)) 

        if proto_buf_type not in PROB_TYPE_DICT:
            self.logfail('The type {} is not supported. '
                          'The supported types are '
                          '{}'.format(proto_buf_type, list(PROB_TYPE_DICT.keys()))) 
            return -1
            
        return proto_buf_type
