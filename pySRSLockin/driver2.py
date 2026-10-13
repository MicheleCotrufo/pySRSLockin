import pyvisa as visa

class SRS_Lockin:
    #Models currently supported: SR865A, SR810
    
        
    #The list model_identifiers is used to identify a device as a SRS lockin, and to detect its model.
    #Each element of the list is a list of two strings. If the second string is contained in the device identity (i.e. the answer to '*IDN?')
    #then the model device is given by the first string
    model_identifiers = [
                        ['SR865A',  'Stanford_Research_Systems,SR865A'],
                        ['SR844',   'Stanford_Research_Systems,SR844'],
                        ['SR810',   'Stanford_Research_Systems,SR810'],
                        ['SR510',   'Stanford_Research_Systems,SR510']
                        ]
                        
    new_models = ['SR865A','SR844','SR810'] #Devices in this list support the '*IDN?' and other "standardized" commands
    old_models = ['SR510'] #Devices in this list do not support the '*IDN?' and other "standardized" commands

    #Each device has a different set of available sensitivies and time constants. Moreover, they ways that the values are associated to an integer index
    #might differt between devices. To keep the code general, we define for each device a dictionary of sensitivies and a dictionary of time constants. 
    # The keys of each dictionary correspond to the integer value that each device associates to a particular sensitivity or time constant when reading/setting it.
    #For example, for device SR865A, there are 22 possible values of time constants, arranged from  1e-6s (dictionary key i=0) to 30e3s (index i=22)
    #However, for the same device the sensitivies are arranged in  decreasing values. There are 28 possible values of sensitivities, 
    # arranged from  1V (index i=0) to 1e-9V (index i=27)

    _sensitivities = {
        'SR865A':dict(enumerate([1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9,
        500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6,
        200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
        50e-3, 100e-3, 200e-3, 500e-3, 1][::-1])), #NOTE: in the model SR865A the sensitivies are arranged in descreasing order
        'SR844':dict(enumerate([100e-9, 300e-9, 1e-6, 3e-6, 10e-6, 30e-6, 100e-6,
        300e-6, 1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1])),
        'SR810':dict(enumerate([2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9,
        500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6,
        200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
        50e-3, 100e-3, 200e-3, 500e-3, 1])),
        'SR510':dict(enumerate([10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9, 1e-6, 2e-6, 5e-6, 
        10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
        50e-3, 100e-3, 200e-3, 500e-3], start=1)),
    }
    _time_constants = {
        'SR865A':[1e-6, 3e-6, 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3,
        30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3,
        3e3, 10e3, 30e3],
        'SR844':[100e-6, 300e-6, 1e-3, 3e-3, 10e-3,
        30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3,
        3e3, 10e3, 30e3],
        'SR810':[10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3,
        30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3,
        3e3, 10e3, 30e3],
        'SR510':[1e-3, 3e-3, 10e-3,30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100],
    }

    #Different devices might need different commands to retrieve the same data. To keep the code short and tidy,
    #we define a mapping dictionary. Each element of the dictionary has the format
    # 'PropertyName': {'Model1':'Command to send to Model 1 to get this property', 'Model2':'Command to send to Model 2 to get this property', etc}
    #For older models, the template commmand for reading/setting properties is not always consistent (e.g., model SR510, commands to read/set sensitivity and time constants). 
    #To address this, certain properties are mapped twice, once for reading and once for setting
    mapping_properties = {
    'X':                        {'SR865A':'OUTP? 0',            'SR844':'OUTP? 1',              'SR810':'OUTP? 1'           'SR510':' S0;Q'},
    'Y':                        {'SR865A':'OUTP? 1',            'SR844':'OUTP? 2',              'SR810':'OUTP? 2'                          },
    'mag':                      {'SR865A':'OUTP? 2',            'SR844':'OUTP? 3',              'SR810':'OUTP? 3'                          },
    'theta':                    {'SR865A':'OUTP? 3',            'SR844':'OUTP? 5',              'SR810':'OUTP? 4'                          },
    'aux1':                     {'SR865A':'OAUX? 0',            'SR844':'AUXI? 1',              'SR810':'OAUX? 1'                          },
    'aux2':                     {'SR865A':'OAUX? 1',            'SR844':'AUXI? 2',              'SR810':'OAUX? 2'                          },
    'value_shown_output_LCD':   {                                                                                           'SR510':' Q'},
    'time_constant_READ':       {'SR865A':'OFLT?',              'SR844':'OFLT?',                'SR810':'OFLT?',            'SR510':' T1'},
    'time_constant_SET':        {'SR865A':'OFLT [VALUE]',       'SR844':'OFLT [VALUE]',         'SR810':'OFLT [VALUE]',     'SR510':' T1,[VALUE]'},
    'sensitivity_READ':         {'SR865A':'SCAL?',              'SR844':'SENS?',                'SR810':'SENS?',            'SR510':' G'},
    'sensitivity_SET':          {'SR865A':'SCAL [VALUE]',       'SR844':'SENS [VALUE]',         'SR810':'SENS  [VALUE]',    'SR510':' G[VALUE]'},
    'frequency_READ':           {'SR865A':'FREQ?',              'SR844':'FREQ?',                'SR810':'FREQ?',            'SR510':' F'},
    'frequency_SET':            {'SR865A':'FREQ [VALUE]',       'SR844':'FREQ [VALUE]',         'SR810':'FREQ [VALUE]',     'SR510':' F[VALUE]'},
    'phase_READ':               {'SR865A':'PHAS?',              'SR844':'PHAS?',                'SR810':'PHAS?',            'SR510':' P'},,
    'phase_SET':                {'SR865A':'PHAS [VALUE]',       'SR844':'PHAS [VALUE]',         'SR810':'PHAS [VALUE]',     'SR510':' P[VALUE]'},
    'auto_sensitivity':         {'SR865A':'ASCL',               'SR844':'AGAN',                 'SR810':'AGAN'}
    }

    
    def __init__(self,model=None,only_new_models=False):
        '''
        model, str
            If model is specified, the driver will only look for devices of this model. If the specified model is not within the supported models
            (i.e. in the model_identifiers list, an error is raised)
        only_new_models, bool
            Older models (e.g. SR510) use a different set of commands, and they do not have a easy way to be "identified". The identification can be done indirectly
            by testing their response to different commands. However, this slows down the methods list_devices() and connect_device().
            If only_new_models is set to True, older models are ignored.
        '''
        self.only_new_models = only_new_models
        self.list_supported_models = [model[0] for model in self.model_identifiers]
        if model:
            if not(model in self.list_supported_models):
                   raise RuntimeError("The specified model is not supported. Supported models are " + ", ".join(models_supported))
        self.model_user = model #model specified by user
        self.rm = visa.ResourceManager()
        self.model = None #the exact model of the device currently connected. Different models have different specs (e.g. the available time constants) and might use different communication protocols
        self.connected = False
        #A device will be positively identified icontains any of these words
        self._time_constant = None
        
    def check_if_valid_old_SRS_instrument(self,instrument):
        #Old Models (e.g. SR510) do not support the '*IDN?' and other commands. For these models, querying '*IDN?' will return a timeout error. 
        #This method uses other tricks to identify these models.
        
        #Check if it is an SR510
        Qresult = None
        Rresult = None
        Sresult = None
        Qresult = instrument.query(" Q")
        Rresult = instrument.query(' R')
        Sresult = instrument.query(' S')
        
        if Qresult and Rresult and Sresult:
            return (['SR510', 'Stanford_Research_Systems,SR510'])
            
        return None
        
    def additional_checks(self):
        #This routine is called after connection to a device. It performs additional adjustments to the settings depending on the model
        
        #If the model is SR510, the range of possibile sensitivities depend on whether there is a pre-amplifier or not.
        #If the pre-amplifier is absent, sensitivities below 100nV are not available.
        #We check the presence of the pre-amplifier with the command ' H', and we adjust the dictionary of sensitivies accordingly.
        
        if self.model == 'SR510':
            Hresult = self.instrument.query(" H")
            if int(Hresult) == 0:
                for key in [1,2,3]:
                     self._sensitivities_this_device.pop(key, None) 
            
        
    def list_devices(self):
        '''
        Scans all potential devices, ask for their identity and check if any of them is a valid device supported by this driver (by comparing their identity with the elements of model_identifiers)

        Returns
        -------
        list_valid_devices, list
            A list of all found valid devices. Each element of the list is a list of three strings, in the format [address,identiy,model]

        '''
        self.list_all_devices = self.rm.list_resources()
        self.list_valid_devices = [] 
        for addr in self.list_all_devices:
            if(not(addr.startswith('ASRL'))):
                try:
                    instrument = self.rm.open_resource(addr)
                    try: #Older Models (e.g. SR510) do not support the '*IDN?' and other commands. For these models, querying '*IDN?' will return a timeout error. We need to use other tricks to identify these models. See the except block.
                        idn = instrument.query('*IDN?').strip()
                        for model in self.model_identifiers: #sweep over all supported models
                            if model[1] in idn:              #check if idn is one of the supported models
                                if self.model_user and not(self.model_user == model[0]): #if the user has specified a specific model, we discard any other model
                                    break
                                self.list_valid_devices.append([addr,idn,model[0]]) 
                    except Exception as Error:
                        if ("VI_ERROR_TMO" in str(Error)) and (self.only_new_models == False): 
                            # Checking if "VI_ERROR_TMO" is in Error is a Quick and dirt way to check if the errors was due to timeout; this needs to be implemented better
                            #In this case, we run additional tests to see if we are dealing with an old model
                            valid_instrument = self.check_if_valid_old_SRS_instrument(instrument)
                            if valid_instrument:
                                if self.model_user and not(self.model_user == valid_instrument[0]): #if the user has specified a specific model, we discard any other model
                                    break
                                self.list_valid_devices.append([addr,valid_instrument[0],valid_instrument[1]])
                    instrument.before_close()
                    instrument.close()    
                except visa.VisaIOError as e:
                    pass
                        
        return self.list_valid_devices

    def connect_device(self,device_addr):
        self.list_devices()
        device_addresses = [dev[0] for dev in self.list_valid_devices]
        device_models = [dev[1] for dev in self.list_valid_devices]
        try:
            index = device_addresses.index(device_addr)
            device_model = device_models[index]
            try:         
                self.instrument = self.rm.open_resource(device_addr)
                if device_model in self.new_models:
                    Msg = self.instrument.query('*IDN?')
                    self.model = device_model
                    ID = 1
                if device_model in self.old_models: #In this case we do not have a way to confirm the identity
                    self.model = device_model
                    Msg = 'Connected (Old Lock-in Model detected)'
                    ID = 1
            except visa.VisaIOError as e:
                Msg = "Error while connecting:" + str(e)
                ID = 0 
        except ValueError:
            raise ValueError("The specified address is not a valid device address.")
        if(ID==1):
            self.connected = True
            self._time_constants_this_device = self._time_constants[self.model]
            self._sensitivities_this_device = self._sensitivities[self.model]
            self.additional_checks()
            #self.read_parameters_upon_connection()
        return (Msg,ID)

    def disconnect_device(self):
        if(self.connected == True):
            try:   
                self.instrument.control_ren(False)  # Disable remote mode
                self.instrument.close()
                ID = 1
                Msg = 'Succesfully disconnected.'
            except Exception as e:
                ID = 0 
                Msg = e
            if(ID == 1):
                self.connected = False
                self._time_constant = None
                self._sensitivity = None
                self._time_constants_this_device = None
                self._sensitivities_this_device = None
            return (Msg,ID)
        else:
            raise RuntimeError("Device is already disconnected.")
            
    def check_valid_connection(self):
        '''
        Verify that a device is currently connected.

        Raises
        ------
        RuntimeError
            If no device is currently connected.
        '''
        if not(self.connected):
            raise RuntimeError("No device is currently connected.")
            
    def check_device_support_property(self, prop):
        if not(self.model in list(self.mapping_properties[name].keys())):
            raise RuntimeError(f"Proerty {name} is not available for this device.")
            

    #The property X,Y,mag,phase are read-only, and they are always returned by quering 
    #the instrument with the string given by self.mapping_properties[name][self.model] (where name = 'X','Y', etc.)
    #To keep code short we define a general property (returned by the function output_property) which creates the properties X,Y,mag and phase
    def output_property(name):
        @property
        def prop(self):
            self.check_valid_connection()
            self.check_device_support_property(name)
            return float(self.instrument.query(self.mapping_properties[name][self.model]))
        return prop   

    X,Y,mag,theta = output_property('X'),output_property('Y'),output_property('mag'),output_property('theta')
    aux1,aux2 = output_property('aux1'),output_property('aux2')
    
    @property
    def time_constants(self):
        self.check_valid_connection()
        return self._time_constants_this_device 
    
    @property
    def sensitivities(self):
        self.check_valid_connection()
        return self._sensitivities_this_device

    @property
    def frequency(self):
        self.check_valid_connection()
        return float(self.instrument.query(self.mapping_properties['frequency'][self.model] + self._end_character_queries))

    @property
    def phase(self):
        self.check_valid_connection()
        return float(self.instrument.query(self.mapping_properties['phase'][self.model] + self._end_character_queries))

    @property
    def time_constant(self):
        self.check_valid_connection()

        try:
            Msg = self.instrument.query(self.mapping_properties['time_constant'][self.model]+ self._end_character_queries)
            self._time_constant = int(Msg)
            return self._time_constant
        except:
            return None

    @time_constant.setter
    def time_constant(self, time_constant):
        '''
        time_constant, int
            integer which defines the desired time_constant, based on the mapping specified in the array self._time_constants
        '''
        self.check_valid_connection()

        if time_constant<0 or time_constant>len(self.time_constants):
            raise ValueError(f"Time_constant must be an intenger between 0 and {len(self.time_constants)}.")
        self.instrument.write(self.mapping_properties['time_constant_setting'][self.model] + self._divider + str(time_constant))
        self._time_constant = time_constant 
        return self._time_constant 
    
    @property
    def sensitivity(self):
        self.check_valid_connection()
        try:
            Msg = self.instrument.query(self.mapping_properties['sensitivity'][self.model]+ self._end_character_queries)
            self._sensitivity = int(Msg)
            return self._sensitivity
        except:
            return None
        
    @sensitivity.setter
    def sensitivity(self, sensitivity):
        '''
        sensitivity, int
            integer which defines the desired sensitivity, based on the mapping specified in the dictionary self.sensitivities
        '''
        self.check_valid_connection()
        
        if not sensitivity in list(self.sensitivities.keys()):
            raise ValueError(f"The input argument (sensitivity index) must be one of these values: {list(self.sensitivities.keys())}.")
        self.instrument.write(self.mapping_properties['sensitivity'][self.model] + self._divider + str(sensitivity))
        self._sensitivity = sensitivity
        return self._sensitivity

    def set_auto_scale(self):
        self.check_valid_connection()
        try:
            ID = self.instrument.write(self.mapping_properties['auto_sensitivity'][self.model])
        except visa.VisaIOError:
            ID = 0
            pass
        return ID


        