import os
import PyQt5
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname, 'plugins', 'platforms')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
import PyQt5.QtWidgets as Qt# QApplication, QWidget, QMainWindow, QPushButton, QHBoxLayout
import PyQt5.QtGui as QtGui
import PyQt5.QtCore as QtCore
import logging
import sys
import argparse

import abstract_instrument_interface
import pySRSLockin.driver 

graphics_dir = os.path.join(os.path.dirname(__file__), 'graphics')

##This application follows the model-view-controller paradigm, but with the view and controller defined inside the same object (the GUI)
##The model is defined by the class 'interface', and the view+controller is defined by the class 'gui'. 

class interface(abstract_instrument_interface.abstract_interface):
    """
    Create a high-level interface with the device, validates input data and perform high-level tasks such as periodically reading data from the instrument.
    It uses signals (i.e. QtCore.pyqtSignal objects) to notify whenever relevant data has changes. These signals are typically received by the GUI
    Several general-purpose attributes and methods are defined in the class abstract_interface defined in abstract_instrument_interface
    ...

    Attributes specific for this class (see the abstract class abstract_instrument_interface.abstract_interface for general attributes)
    ----------
    instrument
        Instance of driver.pySRSLockin
    connected_device_name : str
        Name of the physical device currently connected to this interface 
    continuous_read : bool 
        When this is set to True, the data from device are acquired continuosly at the rate set by refresh_time
    stored_data : list
        List used to store data acquired by this interface
    settings = {
            'refresh_time': float,      The time interval (in seconds) between consecutive reading from the device driver (default = 0.2)
            'sensitivity_auto': bool    true if software-controlled automatic sensitivity is enabled
            }


    Methods defined in this class (see the abstract class abstract_instrument_interface.abstract_interface for general methods)
    -------
    refresh_list_devices()
        Get a list of compatible devices from the driver. Stores them in self.list_devices, and populates the combobox in the GUI.
    connect_device(device_full_name)
        Connect to the device identified by device_full_name
    disconnect_device()
        Disconnect the currently connected device
    close()
        Closes this interface, close plot window (if any was open), and calls the close() method of the parent class, which typically calls the disconnect_device method
    
    set_disconnected_state()
        
    set_connecting_state()
    
    set_connected_state()
    
    set_refresh_time(refresh_time)
    
    [TO FINISH]

    """
    output = {'X':0,'Y':0,'mag':0,'theta':0,'aux1':0,'aux2':0}  #We define this also as class variable. This makes it possible to see which data is produced by this interface without having to create an object


    ## SIGNALS THAT WILL BE USED TO COMMUNICATE WITH THE GUI
    #                                                                   | Triggered when ...                                        | Parameter(s) Sent  
    #                                                               #   -----------------------------------------------------------------------------------------------------------------------         
    sig_list_devices_updated = QtCore.pyqtSignal(list)              #   | List of devices is updated                                | List of devices   
    sig_refreshtime = QtCore.pyqtSignal(float)                      #   | Refresh time is changed                                   | New value of refresh time
    sig_reading = QtCore.pyqtSignal(int)                            #   | Reading status changes                                    | 1 = Started Reading, 2 = Paused Reading, 3 Stopped Reading 
    sig_updated_data = QtCore.pyqtSignal(object)                    #   | Data is read from instrument                              | Acquired data 
    sig_read_available_time_constants = QtCore.pyqtSignal(list)     #
    sig_read_available_sensitivities = QtCore.pyqtSignal(list)      #
    sig_set_time_constant = QtCore.pyqtSignal(int)                  #
    sig_read_time_constant = QtCore.pyqtSignal(list)                #list of two integers, first is integer index of time constant, second is numerical value of time constant
    sig_set_sensitivity = QtCore.pyqtSignal(int)                    #list of two integers, first is integer index of sensitivity, second is numerical value of sensitivity
    sig_read_sensitivity = QtCore.pyqtSignal(list)                  #list of two integers, first is integer index of sensitivity, second is numerical value of sensitivity
    sig_sensitivity_auto_change = QtCore.pyqtSignal(bool) 
    ##
    # Identifier codes used for view-model communication. Other general-purpose codes are specified in abstract_instrument_interface
    SIG_READING_START = 1
    SIG_READING_PAUSE = 2
    SIG_READING_STOP = 3

    def __init__(self, **kwargs):
        self.output = {'X':0,'Y':0,'mag':0,'theta':0,'aux1':0,'aux2':0} 
        ### Default values of settings (might be overlapped by settings saved in .json files later)
        self.settings = {   'refresh_time': 0.2,        #default refresh rate, in seconds
                            'sensitivity_auto': True    #Boolean, true if software-controlled automatic sensitivity is enabled
                            }

        self.list_devices = []          #list of devices found
        self.continuous_read = False #When this is set to True, the data from device are acquired continuosly at the rate set by self.settings['refresh_time']
        self.stored_data = {'X':[],'Y':[],'mag':[],'theta':[],'aux1':[],'aux2':[]}  # List used to store recorded data
        self.connected_device_name = ''
        
        self.instrument = pySRSLockin.driver.SRS_Lockin() 
  
        super().__init__(**kwargs)
        self.refresh_list_devices()   

############################################################
### Functions to interface the GUI and low-level driver
############################################################

    def refresh_list_devices(self):
        '''
        Get a list of all devices connected, by using the method list_devices() of the driver. For each device obtain its identity and its address.
        '''
        self.logger.info(f"Looking for devices...") 
        list_valid_devices = self.instrument.list_devices()
        self.logger.info(f"Found {len(list_valid_devices)} devices.")
        self.list_devices = list_valid_devices
        self.send_list_devices()

    def send_list_devices(self):
        if(len(self.list_devices)>0):
            list_IDNs_and_devices = [dev[1] + " --> " + dev[0] for dev in self.list_devices] 
        else:
            list_IDNs_and_devices = []
        self.sig_list_devices_updated.emit(list_IDNs_and_devices)

    def connect_device(self,device_full_name):
        if(device_full_name==''): # Check  that the name is not empty
            self.logger.error("No valid device has been selected.")
            return
        self.set_connecting_state()
        device_name = device_full_name.split(' --> ')[1].lstrip() # We extract the device address from the device name
        self.logger.info(f"Connecting to device {device_name}...")
        try:
            (Msg,ID) = self.instrument.connect_device(device_name) # Try to connect by using the method connect_device of the device driver
            if(ID==1):  #If connection was successful
                self.logger.info(f"Connected to device {device_name}.")
                self.connected_device_name = device_name
                self.set_connected_state()
            else: #If connection was not successful
                self.logger.error(f"Error: {Msg}")
                self.set_disconnected_state()
        except Exception as e:
            self.logger.error(f"Error: {e}")
            self.set_disconnected_state()

    def disconnect_device(self):
        self.logger.info(f"Disconnecting from device {self.connected_device_name}...")
        (Msg,ID) = self.instrument.disconnect_device()
        if(ID==1): # If disconnection was successful
            self.logger.info(f"Disconnected from device {self.connected_device_name}.")
            self.continuous_read = 0 # We set this variable to 0 so that the continuous reading from the powermeter will stop
            self.set_disconnected_state()
        else: #If disconnection was not successful
            self.logger.error(f"Error: {Msg}")
            self.set_disconnected_state() #When disconnection is not succeful, it is typically because the device alredy lost connection
                                        #for some reason. In this case, it is still useful to have all widgets reset to disconnected state    
    
    def close(self,**kwargs):
        super().close(**kwargs)                          

    def set_connected_state(self):
        super().set_connected_state()
        self.read_available_time_constants()
        self.read_available_sensitivities()
        self.read_time_constant()
        self.read_sensitivity()
        self.start_reading()

    def set_refresh_time(self, refresh_time):
        try: 
            refresh_time = float(refresh_time)
            if self.settings['refresh_time'] == refresh_time: #in this case the number in the refresh time edit box is the same as the refresh time currently stored
                return True
        except ValueError:
            self.logger.error(f"The refresh time must be a valid number.")
            self.sig_refreshtime.emit(self.settings['refresh_time'])
            return False
        if refresh_time < 0.001:
            self.logger.error(f"The refresh time must be positive and >= 1ms.")
            self.sig_refreshtime.emit(self.settings['refresh_time'])
            return False
        self.logger.info(f"The refresh time is now {refresh_time} s.")
        self.settings['refresh_time'] = refresh_time
        self.sig_refreshtime.emit(self.settings['refresh_time'])
        return True

    def read_available_time_constants(self):
        self.logger.info(f"Reading all possible values of time constants from device...")
        self.time_constants = self.instrument.time_constants
        self.logger.info(f"This device supports {len(self.time_constants)} different time constants.") 
        self.sig_read_available_time_constants.emit(self.time_constants)

    def read_available_sensitivities(self):
        self.logger.info(f"Reading all possible values of sensitivities from device...")
        self.sensitivities = self.instrument.sensitivities
        self.logger.info(f"This device supports {len(self.sensitivities)} different sensitivities.") 
        self.sig_read_available_sensitivities.emit(self.sensitivities)

    def read_time_constant(self):
        self.logger.info(f"Reading current time constant from device {self.connected_device_name}...") 
        self.time_constant = self.instrument.time_constant
        if self.time_constant == None:
            self.logger.error(f"An error occurred while reading the time constant from this device.")
            return
        
        self.sig_read_time_constant.emit([self.time_constant,self.time_constants[self.time_constant]])
        self.logger.info(f"Current time constant is {self.time_constants[self.time_constant]} (index={self.time_constant})...") 

    def read_sensitivity(self, log= True):
        #when log = False, the message regarding the read of sensitivities is not added to the logs
        #this is useful to avoid excessively polluting the logs when sensitivty is changed very often automatically
        if log:
            self.logger.info(f"Reading current sensitivity from device {self.connected_device_name}...") 
        self.sensitivity = self.instrument.sensitivity
        if self.sensitivity == None:
            self.logger.error(f"An error occurred while reading the sensitivity from this device.")
            return
        #self.gui.combo_Sensitivities.setCurrentIndex(self.sensitivity)
        self.sig_read_sensitivity.emit([self.sensitivity,self.sensitivities[self.sensitivity]])  
        if log:
            self.logger.info(f"Current sensitivity is {self.sensitivities[self.sensitivity]} (index={self.sensitivity})...") 
        
    def set_time_constant(self,tc): 
        if tc == self.time_constant:
            return
        self.logger.info(f"Setting time constant to {self.time_constants[tc]}  (index={tc})...")
        try: 
            self.instrument.time_constant = tc #set time constant
            tcnew = self.instrument.time_constant #read again time constant to confirm that it changed
            if tcnew == tc:
                self.logger.info(f"Time constant changed to {self.time_constants[tc]} (old value was {self.time_constants[self.time_constant]}).")
                self.time_constant = tc
                self.sig_set_time_constant.emit(self.time_constant)
            else:
                self.logger.error(f"The driver did not raise any error, but it was not possible to change the time constant.")
        except Exception as e:
            self.logger.error(f"An error occurred while setting the time constant: {e}")
            return False
        return True

    def set_sensitivity(self,s, log = True): 
        #when log = False, the message regarding the change of sensitivities is not added to the logs
        #this is useful to avoid excessively polluting the logs when sensitivty is changed very often automatically
        if s == self.sensitivity:
            return
        if log:
            self.logger.info(f"Setting sensitivity to {self.sensitivities[s]}  (index={s})...")
        try: 
            s_old = self.sensitivity
            self.instrument.sensitivity = s #set sensitivity
            self.read_sensitivity(log = log) #read again sensitivity to store it into self.sensitivity and to make sure that combobox is updated
            s_new = self.sensitivity #read new sensitivity
            if s_new == s:
                self.sig_set_sensitivity.emit(self.sensitivity)
                if log:
                    self.logger.info(f"Sensitivity changed to {self.sensitivities[s]} (old value was {self.sensitivities[s_old]}).")
            else:
                self.logger.error(f"The driver did not raise any error, but it was not possible to change the sensitivity.")
        except Exception as e:
            self.logger.error(f"An error occurred while setting the sensitivity: {e}")
            return False
        return True

    def set_auto_scale(self):
        ID = self.instrument.set_auto_scale()
        if ID==0:
            self.logger.error(f"It was not possible to set 'auto scale'. This device model might not support it.")
        else:
            self.logger.info(f"'auto scale' set correctly.")

    def set_sensitivity_auto(self,status):
        self.settings['sensitivity_auto'] = status
        if status==True:
            self.logger.info(f"Auto-adjustement sensitivity (via software) set to ON.")
            if self.instrument.connected == True:
                self.read_sensitivity() #make sure to read the current value of sensitivity
        else:
            self.logger.info(f"Auto-adjustement sensitivity (via software) set to OFF.")
        self.sig_sensitivity_auto_change.emit(self.settings['sensitivity_auto'])

    def adjust_sensitivity_auto(self):
        ''' Automatically adjust the sensitivity of the instrument based on the current value of magnitude.
            It checks if the current magnitude value is above 20% and below 80% of the current sensitivity range.
            If not, it adjust the sensitivity range to the smallest one such that the current value of magnitude is below 80% of it.
        '''
        max_bound = 0.8
        min_bound = 0.2
        current_mag = self.output['mag']
        current_sensitivity_index = self.sensitivity
        current_sensitivity_value = self.sensitivities[self.sensitivity]
        if (current_sensitivity_value*min_bound) < current_mag < (current_sensitivity_value*max_bound):
            return False #In this case we don't need to change the sensitivity
        else:
            #self.logger.info(f"Need to adjust sensitivity.")
            target_sensitivity = current_mag / max_bound
            #Look for smallest sensitivity larger than target_sensitivity
            list_possible_sensitivies = [i for i in  self.sensitivities if i > target_sensitivity]
            if list_possible_sensitivies:
                new_sensitivity = min(list_possible_sensitivies)
            else:
                new_sensitivity = max(self.sensitivities)
            index_new_sensitivity = self.sensitivities.index (new_sensitivity)
            return self.set_sensitivity(index_new_sensitivity,log = False)

    def start_reading(self):
        if(self.instrument.connected == False):
            self.logger.error(f"No device is connected.")
            return
        #self.logger.info(f"Updating wavelength and refresh time before starting reading...")       
        self.sig_reading.emit(self.SIG_READING_START) # This signal will be caught by the GUI
        self.continuous_read = True #Until this variable is set to True, the function UpdatePower will be repeated continuosly 
        self.logger.info(f"Starting reading from device {self.connected_device_name}...")
        # Call the function self.update(), which will do stome suff (read power and store it in a global variable) and then call itself continuosly until the variable self.continuous_read is set to False
        self.update()
        return
 
    def pause_reading(self):
        #Sets self.continuous_read to False (this will force the function update() to stop calling itself)
        self.continuous_read = False
        self.logger.info(f"Paused reading from device {self.connected_device_name}.")
        self.sig_reading.emit(self.SIG_READING_PAUSE) # This signal will be caught by the GUI
        return

    def stop_reading(self):
        #Sets self.continuous_read to False (this will force the function update() to stop calling itself) and delete all accumulated data
        self.continuous_read = False
        self.stored_data = []
        self.update() #We call one more time the self.update() function to make sure plots is cleared. Since self.continuous_read is already set to False, update() will not acquire data anymore
        self.logger.info(f"Stopped reading from device {self.connected_device_name}. All stored data have been deleted.")
        self.sig_reading.emit(self.SIG_READING_PAUSE) # This signal will be caught by the GUI
        # ...
        return
        
    def update(self):
        '''
        This routine reads continuosly the data from the device and store the values
        If we are continuosly acquiring (i.e. if self.ContinuousRead = 1) then:
            1) Reads data from device object and stores it in the self.output dictionary
            2) Update the value of the corresponding edits widgets in the GUI
            3) Call itself after a time given by self.settings['refresh_time']
        '''
        #self.plot_object.data.setData(list(range(1, len(self.stored_powers)+1)), self.stored_powers) #This line is executed even when self.continuous_read == False, to make sure that plot gets cleared when user press the stop button
        if(self.continuous_read == True):
            (X,Y,mag,theta,aux1,aux2) = self.instrument.X,self.instrument.Y,self.instrument.mag,self.instrument.theta,self.instrument.aux1,self.instrument.aux2
            self.output['X'] = X
            self.output['Y'] = Y
            self.output['mag'] = mag
            self.output['theta'] = theta
            self.output['aux1'] = aux1
            self.output['aux2'] = aux2
            for k in self.output.keys():	
                self.stored_data[k].append(self.output[k])

            super().update()

            if self.settings['sensitivity_auto'] == True:
                self.adjust_sensitivity_auto()

            self.sig_updated_data.emit(self.output)
            QtCore.QTimer.singleShot(int(self.settings['refresh_time']*1e3), self.update)
           
        return

############################################################
### END Functions to interface the GUI and low-level driver
############################################################

class gui(abstract_instrument_interface.abstract_gui):
    def __init__(self,interface,parent):
        """
        Attributes specific for this class (see the abstract class abstract_instrument_interface.abstract_gui for general attributes)
        ----------
        ...
        """
        super().__init__(interface,parent)
        self.initialize()

    def initialize(self):
        self.create_widgets()
        self.connect_widgets_events_to_functions()

        ### Call the initialize method of the parent class
        super().initialize()

        ### Connect signals from model to event slots of this GUI
        self.interface.sig_list_devices_updated.connect(self.on_list_devices_updated)
        self.interface.sig_connected.connect(self.on_connection_status_change) 
        self.interface.sig_reading.connect(self.on_reading_status_change) 
        self.interface.sig_updated_data.connect(self.on_data_change) 
        self.interface.sig_sensitivity_auto_change.connect(self.on_sensitivity_auto_change) 
        self.interface.sig_read_available_time_constants.connect(self.on_list_time_constants_change)
        self.interface.sig_read_available_sensitivities.connect(self.on_list_sensitivities_change)
        self.interface.sig_read_time_constant.connect(self.on_time_constant_change)
        self.interface.sig_read_sensitivity.connect(self.on_sensitivity_change)
        self.interface.sig_refreshtime.connect(self.on_refreshtime_change)
        self.interface.sig_close.connect(self.on_close)

        ### SET INITIAL STATE OF WIDGETS
        self.edit_RefreshTime.setText(f"{self.interface.settings['refresh_time']:.3f}")
        self.interface.send_list_devices()  
        if self.interface.settings['sensitivity_auto']:
            self.box_SensitivityAuto.setChecked(True)
        self.on_connection_status_change(self.interface.SIG_DISCONNECTED) #When GUI is created, all widgets are set to the "Disconnected" state    
        ###

    def create_widgets(self):
        """
        Creates all widgets and layout for the GUI. Any Widget and Layout must assigned to self.containter, which is a pyqt Layout object
        """ 
        self.container = Qt.QVBoxLayout()

        #Use the custom connection/listdevices panel, defined in abstract_instrument_interface.abstract_gui
        hbox1, widgets_dict = self.create_panel_connection_listdevices()
        for key, val in widgets_dict.items(): 
            setattr(self,key,val) 

        hbox2 = Qt.QHBoxLayout()
 
        self.label_RefreshTime = Qt.QLabel("Refresh time (s): ")
        self.label_RefreshTime.setToolTip('Specifies how often data is read from the device (Minimum value = 0.001 s).') 
        self.edit_RefreshTime  = Qt.QLineEdit()
        self.edit_RefreshTime.setText(f"{self.interface.settings['refresh_time']:.3f}")
        self.edit_RefreshTime.setToolTip('Specifies how often data is read from the device (Minimum value = 0.001 s).') 
        self.edit_RefreshTime.setAlignment(QtCore.Qt.AlignRight)
        self.button_SetAutoScale = Qt.QPushButton("Set Auto Scale")
        self.label_TimeConstants = Qt.QLabel("Time constant (s): ")
        self.combo_TimeConstants = Qt.QComboBox()
        self.label_Sensitivities = Qt.QLabel("Sensitivity (V): ")
        self.combo_Sensitivities = Qt.QComboBox()
        self.box_SensitivityAuto = Qt.QCheckBox("Auto Sensitivity (Software)")
        self.box_SensitivityAuto.setToolTip('Enables a software-controlled adjustement of sensitivity.')

        widgets_row2 = [self.label_RefreshTime,self.edit_RefreshTime,self.button_SetAutoScale,
                            self.label_TimeConstants,self.combo_TimeConstants,self.label_Sensitivities,self.combo_Sensitivities,
                            self.box_SensitivityAuto]
        widgets_row2_stretches = [0]*len(widgets_row2)
        for w,s in zip(widgets_row2,widgets_row2_stretches):
            hbox2.addWidget(w,stretch=s)
        hbox2.addStretch(1)

        hbox3 = Qt.QHBoxLayout()
        hbox3_vbox1 = Qt.QVBoxLayout()
        
        self.button_StartPauseReading = Qt.QPushButton("")
        self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'play.png')))
        self.button_StartPauseReading.setToolTip('Start or pause the reading from the device. The previous data points are not discarded when pausing.') 

        hbox3_vbox1_hbox1 = Qt.QHBoxLayout()
        hbox3_vbox1_hbox1.addWidget(self.button_StartPauseReading)  
     
        #hbox3_vbox1_hbox2 = Qt.QHBoxLayout()
        #hbox3_vbox1_hbox2.addWidget(self.label_RefreshTime)  
        #hbox3_vbox1_hbox2.addWidget(self.edit_RefreshTime,stretch=1)

        hbox3_vbox1.addLayout(hbox3_vbox1_hbox1)
        #hbox3_vbox1.addLayout(hbox3_vbox1_hbox2)

        fontLabel = QtGui.QFont("Times", 10,QtGui.QFont.Bold)
        fontEdit = QtGui.QFont("Times", 10,QtGui.QFont.Bold)

        self.label_Output = dict()    
        self.edit_Output = dict() 
        self.widget_Output = dict()     
        for k in self.interface.output.keys():	#Create display textbox for each of the output data of this interface	
            self.label_Output[k] = Qt.QLabel(f"{k}: ")
            self.label_Output[k].setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignCenter)
            self.label_Output[k].setFont(fontLabel)
            self.edit_Output[k] = Qt.QLineEdit()
            self.edit_Output[k].setFont(fontEdit)
            self.edit_Output[k].setMinimumWidth(60)
            self.edit_Output[k].setAlignment(QtCore.Qt.AlignRight)
            self.edit_Output[k].setReadOnly(True)
            hbox_temp = Qt.QHBoxLayout()
            hbox_temp.addWidget(self.label_Output[k])
            hbox_temp.addWidget(self.edit_Output[k],stretch=1)
            self.widget_Output[k] = Qt.QWidget()
            self.widget_Output[k].setLayout(hbox_temp)

        self.layout_ContainerOutputs = Qt.QGridLayout()
        self.layout_ContainerOutputs.addWidget(self.widget_Output['X'], 0, 0)
        self.layout_ContainerOutputs.addWidget(self.widget_Output['Y'], 1, 0)
        self.layout_ContainerOutputs.addWidget(self.widget_Output['mag'], 0, 1)
        self.layout_ContainerOutputs.addWidget(self.widget_Output['theta'], 1, 1)
        self.layout_ContainerOutputs.addWidget(self.widget_Output['aux1'], 0, 2)
        self.layout_ContainerOutputs.addWidget(self.widget_Output['aux2'], 1, 2)
        self.layout_ContainerOutputs.setSpacing(0)
        self.layout_ContainerOutputs.setContentsMargins(0, 0, 0, 0)
        self.widget_ContainerOutputs = Qt.QWidget()
        self.widget_ContainerOutputs.setLayout(self.layout_ContainerOutputs)

        hbox3.addLayout(hbox3_vbox1)
        hbox3.addWidget(self.widget_ContainerOutputs,stretch=1)
     
        for box in [hbox1,hbox2,hbox3]:
            self.container.addLayout(box)  
        self.container.addStretch(1)

        self.widgets_enabled_when_connected = [self.button_SetAutoScale, 
                                               self.combo_TimeConstants , 
                                               self.label_Sensitivities,
                                               self.combo_Sensitivities,
                                               self.button_StartPauseReading,
                                               #self.button_StopReading,
                                               self.box_SensitivityAuto]

        self.widgets_enabled_when_disconnected = [self.combo_Devices , 
                                                  self.button_RefreshDeviceList]
    
    def connect_widgets_events_to_functions(self):
        self.button_RefreshDeviceList.clicked.connect(self.click_button_refresh_list_devices)
        self.button_ConnectDevice.clicked.connect(self.click_button_connect_disconnect)
        self.button_SetAutoScale.clicked.connect(self.click_button_set_auto_scale)
        self.combo_TimeConstants.activated.connect(self.click_combo_time_constants)
        self.combo_Sensitivities.activated.connect(self.click_combo_sensitivities)
        self.box_SensitivityAuto.stateChanged.connect(self.click_box_SensitivityAuto)
        self.button_StartPauseReading.clicked.connect(self.click_button_StartPauseReading)
        self.edit_RefreshTime.returnPressed.connect(self.press_enter_refresh_time)

###########################################################################################################
### Event Slots. They are normally triggered by signals from the model, and change the GUI accordingly  ###
###########################################################################################################

    def on_connection_status_change(self,status):
        if status == self.interface.SIG_DISCONNECTED:
            self.disable_widget(self.widgets_enabled_when_connected)
            self.enable_widget(self.widgets_enabled_when_disconnected)
            self.button_ConnectDevice.setText("Connect")
        if status == self.interface.SIG_DISCONNECTING:
            self.disable_widget(self.widgets_enabled_when_connected)
            self.enable_widget(self.widgets_enabled_when_disconnected)
            self.button_ConnectDevice.setText("Disconnecting...")
        if status == self.interface.SIG_CONNECTING:
            self.disable_widget(self.widgets_enabled_when_connected)
            self.enable_widget(self.widgets_enabled_when_disconnected)
            self.button_ConnectDevice.setText("Connecting...")
        if status == self.interface.SIG_CONNECTED:
            self.enable_widget(self.widgets_enabled_when_connected)
            self.disable_widget(self.widgets_enabled_when_disconnected)
            self.button_ConnectDevice.setText("Disconnect")

    def on_reading_status_change(self,status):
        if status == self.interface.SIG_READING_PAUSE:
            self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'play.png')))
        if status == self.interface.SIG_READING_START:
            self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'pause.png')))
        if status == self.interface.SIG_READING_STOP: 
            self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'play.png')))

    def on_list_devices_updated(self,list_devices):
        self.combo_Devices.clear()  #First we empty the combobox  
        self.combo_Devices.addItems(list_devices) 

    def on_data_change(self,data):
    #    #Data is (in this case) a list
        for k in data.keys():
            try:
                self.edit_Output[k].setText(f"{data[k]:.2e}")
            except:
                self.edit_Output[k].setText(f"nan")

    def on_list_time_constants_change(self,time_constants):
        self.combo_TimeConstants.clear() #First we empty the combobox
        if len(time_constants)>0:
            self.combo_TimeConstants.addItems([str(tc) for tc in time_constants])  

    def on_list_sensitivities_change(self,sensitivities):
        self.combo_Sensitivities.clear() #First we empty the combobox
        if len(sensitivities)>0:
                self.combo_Sensitivities.addItems([str(s) for s in sensitivities])

    def on_time_constant_change(self,t):
        self.combo_TimeConstants.setCurrentIndex(t[0])

    def on_sensitivity_change(self,s):
        self.combo_Sensitivities.setCurrentIndex(s[0])
         
    def on_refreshtime_change(self,value):
        self.edit_RefreshTime.setText(f"{value:.3f}")

    def on_sensitivity_auto_change(self,value):
        self.box_SensitivityAuto.blockSignals(True)
        self.box_SensitivityAuto.setChecked(value)
        self.box_SensitivityAuto.blockSignals(False)

    def on_close(self):
        pass

#######################
### END Event Slots ###
#######################

###################################################################################################################################################
### GUI Events Functions. They are triggered by direct interaction with the GUI, and they call methods of the interface (i.e. the model) object.###
###################################################################################################################################################

    def click_button_refresh_list_devices(self):
        self.interface.refresh_list_devices()

    def click_button_connect_disconnect(self):
        if(self.interface.instrument.connected == False): # We attempt connection   
            device_full_name = self.combo_Devices.currentText() # Get the device name from the combobox
            self.interface.connect_device(device_full_name)
        elif(self.interface.instrument.connected == True): # We attempt disconnection
            self.interface.disconnect_device()
            
    def click_button_set_auto_scale(self):
        self.interface.set_auto_scale()

    def click_combo_time_constants(self):
        self.interface.set_time_constant(self.combo_TimeConstants.currentIndex())

    def click_combo_sensitivities(self):
        self.interface.set_sensitivity(self.combo_Sensitivities.currentIndex())

    def click_box_SensitivityAuto(self,state):
        if state == QtCore.Qt.Checked:
            status_bool = True
        else:
            status_bool = False
        self.interface.set_sensitivity_auto(status_bool)
        return
       
    def click_button_StartPauseReading(self): 
        if(self.interface.continuous_read == False):
            self.interface.start_reading()
        elif (self.interface.continuous_read == True):
            self.interface.pause_reading()
        return

    def click_button_StopReading(self):
        self.stop_reading()

    def press_enter_refresh_time(self):
        return self.interface.set_refresh_time(self.edit_RefreshTime.text())

############################################################
### END GUI Events Functions
############################################################

 
class MainWindow(Qt.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(__package__)
        # Set the central widget of the Window.
        # self.setCentralWidget(self.container)
    def closeEvent(self, event):
        pass

def main():
    parser = argparse.ArgumentParser(description = "",epilog = "")
    parser.add_argument("-s", "--decrease_verbose", help="Decrease verbosity.", action="store_true")
    args = parser.parse_args()

    app = Qt.QApplication(sys.argv)
    window = MainWindow()
    Interface = interface(app=app) #In this case window is both the MainWindow and the parent of the gui
    Interface.verbose = not(args.decrease_verbose)
    app.aboutToQuit.connect(Interface.close) 
    view = gui(interface = Interface, parent=window) #In this case window is the parent of the gui
    window.show()
    app.exec()# Start the event loop.

if __name__ == '__main__':
    main()
