import pyvisa as visa

class SRS_Lockin:
    #Models currently supported: SR865A, SR810
    
        
    #The list model_identifiers is used to identify a device as a SRS lockin, and to detect its model.
    #Each element of the list is a list of two strings. If the second string is contained in the device identity (i.e. the answer to '*IDN?')
    #then the model device is given by the first string
    model_identifiers = [
                        ['SR865A',  'Stanford_Research_Systems,SR865A'],
                        ['SR844',   'Stanford_Research_Systems,SR844'],
                        ['SR810',   'Stanford_Research_Systems,SR810']
                        ]

    #Each device has a different set of available sensitivies and time constants. Moreover, they ways that the values are associated to an integer index
    #might differt between devices. To keep the code general, we define for each device a list of sensitivies and time constants
    #For example, for device SR865A, there are 22 possible values of time constants, arranged from  1e-6s (index i=0) to 30e3s (index i=22)
    #However, for the same device the sensitivies are arranged in  decreasing values. There are 28 possible values of sensitivities, 
    # arranged from  1V (index i=0) to 1e-9V (index i=27)

    _sensitivities = {
        'SR865A':[1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9,
        500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6,
        200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
        50e-3, 100e-3, 200e-3, 500e-3, 1][::-1], #NOTE: in the model SR865A the sensitivies are arranged in descreasing order
        'SR844':[100e-9, 300e-9, 1e-6, 3e-6, 10e-6, 30e-6, 100e-6,
        300e-6, 1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1],
        'SR810':[2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9,
        500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6,
        200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
        50e-3, 100e-3, 200e-3, 500e-3, 1],
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
        3e3, 10e3, 30e3]
    }


    #Different devices might need different commands to retrieve the same data. To keep the code short and tidy,
    #we define a mapping dictionary. Each element of the dictionary has the format
    # 'PropertyName': {'Model1':'Command to send to Model 1 to get this property', 'Model2':'Command to send to Model 2 to get this property', etc}
    mapping_properties = {
                            'X':                        {'SR865A':'OUTP? 0',    'SR844':'OUTP? 1',      'SR810':'OUTP? 1'},
                            'Y':                        {'SR865A':'OUTP? 1',    'SR844':'OUTP? 2',      'SR810':'OUTP? 2'},
                            'mag':                      {'SR865A':'OUTP? 2',    'SR844':'OUTP? 3',      'SR810':'OUTP? 3'},
                            'theta':                    {'SR865A':'OUTP? 3',    'SR844':'OUTP? 5',      'SR810':'OUTP? 4'},
                            'aux1':                     {'SR865A':'OAUX? 0',    'SR844':'AUXI? 1',      'SR810':'OAUX? 1'},
                            'aux2':                     {'SR865A':'OAUX? 1',    'SR844':'AUXI? 2',      'SR810':'OAUX? 2'},
                            'time_constant':            {'SR865A':'OFLT',       'SR844':'OFLT',         'SR810':'OFLT'},
                            'sensitivity':              {'SR865A':'SCAL',       'SR844':'SENS',         'SR810':'SENS'},
                            'frequency':                {'SR865A':'FREQ',       'SR844':'FREQ',         'SR810':'FREQ'},
                            'phase':                    {'SR865A':'PHAS',       'SR844':'PHAS',         'SR810':'PHAS'},
                            'auto_sensitivity':         {'SR865A':'ASCL',       'SR844':'AGAN',         'SR810':'AGAN'}
                            }

    def __init__(self,model=None):
        '''
        If model is specified, the driver will only look for devices of this model. If the specified model is not within the supported models
        (i.e. in the model_identifiers list, an error is raised)
        '''
        if model:
            models_supported = [model[0] for model in self.model_identifiers] 
            if not(model in models_supported):
                   raise RuntimeError("The specified model is not supported. Supported models are " + ", ".join(models_supported))
        self.model_user = model #model specified by user
        self.rm = visa.ResourceManager()
        self.model = None #the exact model of the device currently connected. Different models have different specs (e.g. the available time constants) and might use different communication protocols
        self.connected = False
        #A device will be positively identified icontains any of these words
        self._time_constant = None

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
                    idn = instrument.query('*IDN?').strip()
                    for model in self.model_identifiers: #sweep over all supported models
                        if model[1] in idn:              #check if idn is one of the supported models
                            if self.model_user  and not(self.model_user ==model[0]): #if the user had specified a specific model, we dont consider any other model
                                break
                            self.list_valid_devices.append([addr,idn,model[0]])
                    instrument.before_close()
                    instrument.close()     
                except visa.VisaIOError:
                    pass
        return self.list_valid_devices

    def connect_device(self,device_addr):
        self.list_devices()
        device_addresses = [dev[0] for dev in self.list_valid_devices]
        if (device_addr in device_addresses):
            try:         
                self.instrument = self.rm.open_resource(device_addr)
                Msg = self.instrument.query('*IDN?')
                for model in self.model_identifiers:
                    if model[0] in Msg:
                        self.model = model[0]
                ID = 1
            except visa.VisaIOError:
                Msg = "Error while connecting."
                ID = 0 
        else:
            raise ValueError("The specified address is not a valid device address.")
        if(ID==1):
            self.connected = True
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
            if(ID==1):
                self.connected = False
            return (Msg,ID)
        else:
            raise RuntimeError("Device is already disconnected.")

    #The property X,Y,mag,phase are read-only, and they are always returned by quering 
    #the instrument with the string given by self.mapping_properties[name][self.model] (where name = 'X','Y', etc.)
    #To keep code short we define a general property (returned by the function output_property) which creates the properties X,Y,mag and phase
    def output_property(name):
        @property
        def prop(self):
            if not(self.connected):
                raise RuntimeError("No device is currently connected.")
            return float(self.instrument.query(self.mapping_properties[name][self.model]))
        return prop   

    X,Y,mag,theta = output_property('X'),output_property('Y'),output_property('mag'),output_property('theta')
    aux1,aux2 = output_property('aux1'),output_property('aux2')
    
    @property
    def time_constants(self):
        if not(self.connected):
            raise RuntimeError("No device is currently connected.")
        return self._time_constants[self.model]
    
    @property
    def sensitivities(self):
        if not(self.connected):
            raise RuntimeError("No device is currently connected.")
        return self._sensitivities[self.model]

    @property
    def frequency(self):
        if not(self.connected):
            raise RuntimeError("No device is currently connected.")
        return float(self.instrument.query(self.mapping_properties['frequency'][self.model]+'?'))

    @property
    def phase(self):
        if not(self.connected):
            raise RuntimeError("No device is currently connected.")
        return float(self.instrument.query(self.mapping_properties['phase'][self.model]+'?'))

    @property
    def time_constant(self):
        if not(self.connected):
            self._time_constant = None
            raise RuntimeError("No device is currently connected.")
        try:
            Msg = self.instrument.query(self.mapping_properties['time_constant'][self.model]+'?')
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
        if not(self.connected):
            self._time_constant = None
            raise RuntimeError("No device is currently connected.")
        #try:
        #    time_constant = float(time_constant)
        #except:
        #    raise TypeError("time_constant value must be a valid number")
        if time_constant<0 or time_constant>len(self.time_constants):
            raise ValueError(f"time_constant must be an intenger between 0 and {len(self.time_constants)}.")
        self.instrument.write(self.mapping_properties['time_constant'][self.model]+' '+ str(time_constant))
        self._time_constant = time_constant 
        return self._time_constant 
    
    @property
    def sensitivity(self):
        if not(self.connected):
            self._time_constant = None
            raise RuntimeError("No device is currently connected.")
        try:
            Msg = self.instrument.query(self.mapping_properties['sensitivity'][self.model]+'?')
            self._sensitivity = int(Msg)
            return self._sensitivity
        except:
            return None
        
    @sensitivity.setter
    def sensitivity(self, sensitivity):
        '''
        sensitivity, int
            integer which defines the desired sensitivity, based on the mapping specified in the array self._sensitivities
        '''
        if not(self.connected):
            self._time_constant = None
            raise RuntimeError("No device is currently connected.")
        #try:
        #    time_constant = float(time_constant)
        #except:
        #    raise TypeError("time_constant value must be a valid number")
        if sensitivity<0 or sensitivity>len(self.sensitivities):
            raise ValueError(f"sensitivity must be an intenger between 0 and {len(self.sensitivities)}.")
        self.instrument.write(self.mapping_properties['sensitivity'][self.model]+' '+ str(sensitivity))
        self._sensitivity = sensitivity
        return self._sensitivity

    def set_auto_scale(self):
        if(self.connected):
            try:
                ID = self.instrument.write(self.mapping_properties['auto_sensitivity'][self.model])
            except visa.VisaIOError:
                ID = 0
                pass
        return ID


        