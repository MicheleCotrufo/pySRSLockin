import PyQt5.QtWidgets as Qt# QApplication, QWidget, QMainWindow, QPushButton, QHBoxLayout
import PyQt5.QtGui as QtGui
import PyQt5.QtCore as QtCore
import logging
import sys
from os import path
import argparse

import abstract_instrument_interface
from pySRSLockin.driver import SRS_Lockin

graphics_dir = path.join(path.dirname(__file__), 'graphics')

class interface(abstract_instrument_interface.abstract_interface):
    """
    Create a high-level interface with the device, and act as a connection between the low-level
    interface (i.e. the driver) and the gui.
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
    refresh_time : float, 
        The time interval (in seconds) between consecutive reeading from the device driver (default = 0.2)
    stored_data : list
        List used to store data acquired by this interface


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
    output = {'X':0,'Y':0,'mag':0,'theta':0} #We define this also as class variable, to make it possible to see which data is produced by this interface without having to create an object

    def __init__(self, **kwargs):
        self.output = {'X':0,'Y':0,'mag':0,'theta':0} #We define this also as class variable, to make it possible to see which data is produced by this interface without having to create an object
        
        ### Default values of settings (might be overlapped by settings saved in .json files later)
        self.settings = {   'refresh_time': 0.2,        #default refresh rate, in seconds
                            'sensitivity_auto': True    #Boolean, true if software-controlled automatic sensitivity is enabled
                            }

        self.list_devices = []          #list of devices found
        self.continuous_read = False #When this is set to True, the data from device are acquired continuosly at the rate set by self.settings['refresh_time']
        self.stored_data = {'X':[],'Y':[],'mag':[],'theta':[]}  # List used to store recorded data
        self.plot_window = None # QWidget object of the widget (i.e. floating window) that will contain the plot
        self.plot_object = None # PlotObject object of the plot where self.store_powers is plotted
        self.connected_device_name = ''
        
        self.instrument = SRS_Lockin() 
        ###
        self.gui_class = gui
        ###
        super().__init__(**kwargs)

############################################################
### Functions to interface the GUI and low-level driver
############################################################

    def refresh_list_devices(self):
        '''
        Get a list of all devices connected, by using the method list_devices() of the driver. For each device obtain its identity and its address.
        For each device, create the string "identity -->  address" and add the string to the corresponding combobox in the GUI 
        '''
        #First we empty the combobox
        self.gui.combo_Devices.clear()
        
        #Then we read the list of devices
        self.logger.info(f"Looking for devices...") 
        list_valid_devices = self.instrument.list_devices()
        if(len(list_valid_devices)>0):
            list_IDNs_and_devices = [dev[1] + " --> " + dev[0] for dev in list_valid_devices] 
            self.gui.combo_Devices.addItems(list_IDNs_and_devices)  
        self.logger.info(f"Found {len(list_valid_devices)} devices.") 

    def connect_device(self,device_full_name):
        if(device_full_name==''): # Check  that the name is not empty
            self.logger.error("No valid device has been selected")
            return
        self.set_connecting_state()
        device_name = device_full_name.split(' --> ')[1].lstrip() # We extract the device address from the device name
        self.logger.info(f"Connecting to device {device_name}...")
        try:
            (Msg,ID) = self.instrument.connect_device(device_name) # Try to connect by using the method ConnectDevice of the device object
        except Exception as e:
            self.logger.error(f"Some error occurred: {e}")
            return
        if(ID==1):  #If connection was successful
            self.logger.info(f"Connected to device {device_name}.")
            self.connected_device_name = device_name
            self.set_connected_state()
            self.start_reading()
        else: #If connection was not successful
            self.logger.error(f"Error: {Msg}")
            self.set_disconnected_state()

    def disconnect_device(self):
        self.logger.info(f"Disconnecting from device {self.connected_device_name}...")
        try:
            (Msg,ID) = self.instrument.disconnect_device()
        except Exception as e:
            self.logger.error(f"Some error occurred: {e}")
            return
        if(ID==1): # If disconnection was successful
            self.logger.info(f"Disconnected from device {self.connected_device_name}.")
            self.continuous_read = 0 # We set this variable to 0 so that the continuous reading from the device will stop
            self.set_disconnected_state()
        else: #If disconnection was not successful
            self.logger.error(f"Error: {Msg}")
            self.set_disconnected_state() #When disconnection is not succeful, it is typically because the device alredy lost connection
                                          #for some reason. In this case, it is still useful to have all widgets reset to disconnected state  
    def close(self,**kwargs):
        if hasattr(self.gui,'plot_window'):
            if self.gui.plot_window:
                self.gui.plot_window.close()
        super().close(**kwargs)      
                                          
    def set_disconnected_state(self):
        self.gui.set_disconnected_state()

    def set_connecting_state(self):
        self.gui.set_connecting_state()

    def set_connected_state(self):
        self.gui.set_connected_state()
        self.populate_combo_time_constants()
        self.read_time_constant()
        self.populate_combo_sensitivities()
        self.read_sensitivity()

    def set_auto_scale(self):
        ID = self.instrument.set_auto_scale()
        if ID==0:
            self.logger.error(f"It was not possible to set 'auto scale'. This device model might not support it.")
        else:
            self.logger.info(f"'auto scale' set correctly.")

    def populate_combo_time_constants(self):
        self.logger.info(f"Reading all possible values of time constants from device...")
        self.time_constants = self.instrument.time_constants
        self.gui.combo_TimeConstants.clear() #First we empty the combobox
        if len(self.time_constants)>0:
                self.gui.combo_TimeConstants.addItems([str(tc) for tc in self.time_constants])  
        self.logger.info(f"The device supports {len(self.time_constants)} different time constants.") 
        
    def populate_combo_sensitivities(self):
        self.logger.info(f"Reading all possible values of sensitivities from device...")
        self.sensitivities = self.instrument.sensitivities
        self.gui.combo_Sensitivities.clear() #First we empty the combobox
        if len(self.sensitivities)>0:
                self.gui.combo_Sensitivities.addItems([str(s) for s in self.sensitivities])  
        self.logger.info(f"The device supports {len(self.sensitivities)} different sensitivities.") 

    def read_time_constant(self):
        self.logger.info(f"Reading current time constant from device {self.connected_device_name}...") 
        self.time_constant = self.instrument.time_constant
        if self.time_constant == None:
            self.logger.error(f"An error occurred while reading the time constant from this device.")
            return
        self.gui.combo_TimeConstants.setCurrentIndex(self.time_constant)
        self.logger.info(f"Current time constant is {self.time_constants[self.time_constant]} (index={self.time_constant})...") 
        
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
            else:
                self.logger.error(f"The driver did not raise any error, but it was not possible to change the time constant.")
        except Exception as e:
            self.logger.error(f"An error occurred while setting the time constant: {e}")
            return False
        return True
    
    def read_sensitivity(self, log= True):
        #when log = False, the message regarding the read of sensitivities is not added to the logs
        #this is useful to avoid excessively polluting the logs when sensitivty is changed very often automatically
        if log:
            self.logger.info(f"Reading current sensitivity from device {self.connected_device_name}...") 
        self.sensitivity = self.instrument.sensitivity
        if self.sensitivity == None:
            self.logger.error(f"An error occurred while reading the sensitivity from this device.")
            return
        self.gui.combo_Sensitivities.setCurrentIndex(self.sensitivity)
        if log:
            self.logger.info(f"Current sensitivity is {self.sensitivities[self.sensitivity]} (index={self.sensitivity})...") 
        
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
                if log:
                    self.logger.info(f"Sensitivity changed to {self.sensitivities[s]} (old value was {self.sensitivities[s_old]}).")
                
            else:
                self.logger.error(f"The driver did not raise any error, but it was not possible to change the sensitivity.")
        except Exception as e:
            self.logger.error(f"An error occurred while setting the sensitivity: {e}")
            return False
        return True

    def set_sensitivty_auto(self,status):
        self.settings['sensitivity_auto'] = status
        if status==True:
            self.read_sensitivity() #make sure to read the current value of sensitivity

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

    def set_refresh_time(self, refresh_time):
        try: 
            refresh_time = float(refresh_time)
            if self.settings['refresh_time'] == refresh_time: #in this case the number in the refresh time edit box is the same as the refresh time currently stored
                return True
        except ValueError:
            self.logger.error(f"The refresh time must be a valid number.")
            self.gui.edit_RefreshTime.setText(f"{self.settings['refresh_time']:.3f}")
            return False
        if refresh_time < 0.001:
            self.logger.error(f"The refresh time must be positive and >= 1ms.")
            self.gui.edit_RefreshTime.setText(f"{self.settings['refresh_time']:.3f}")
            return False
        self.logger.info(f"The refresh time is now {refresh_time} s.")
        self.settings['refresh_time'] = refresh_time
        self.gui.edit_RefreshTime.setText(f"{self.settings['refresh_time']:.3f}")
        return True
   
    def start_reading(self):
        if(self.instrument.connected == False):
            self.logger.error(f"No device is connected.")
            return
        self.logger.info(f"Updating refresh time before starting reading...")
        if not(self.gui.press_enter_refresh_time()): #read the current value in the refresh_time textbox, and validates it. The function returns True/False if refresh_time was valid
            return
        
        self.gui.set_reading_state() # Change some widgets

        self.continuous_read = True #Until this variable is set to True, the function Update will be repeated continuosly 
        self.logger.info(f"Starting reading from device {self.connected_device_name}...")
        # Call the function self.Update(), which will do some suff (read data from device and store it in a global variable) and then call itself continuosly until the variable self.ContinuousRead is set back to 0
        self.update()
        return
 
    def pause_reading(self):
        #Sets self.ContinuousRead to 0 (this will force the function Update() to stop calling itself)
        self.continuous_read = False
        self.logger.info(f"Paused reading from device {self.connected_device_name}.")
        self.gui.set_pause_state() # Change some widgets
        return

    def stop_reading(self):
        #Sets self.ContinuousRead to 0 (this will force the function Update() to stop calling itself)
        self.continuous_read = False
        self.stored_powers = []
        self.update() #We call one more time the self.Update() function to make sure plots is cleared. Since self.continuous_read is already set to False, Update() will not acquire data anymore
        self.logger.info(f"Stopped reading from device {self.connected_device_name}. All stored data have been deleted.")
        self.gui.set_stopped_state() # Change some widgets
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
            (X,Y,mag,theta) = self.instrument.X,self.instrument.Y,self.instrument.mag,self.instrument.theta
            self.output['X'] = X
            self.output['Y'] = Y
            self.output['mag'] = mag
            self.output['theta'] = theta
            for k in self.output.keys():	
                self.stored_data[k].append(self.output[k])

            super().update()

            for k in self.output.keys():
                try:
                    self.gui.edit_Output[k].setText(f"{self.output[k]:.2e}")
                except:
                    self.gui.edit_Output[k].setText(f"nan")

            if self.settings['sensitivity_auto'] == True:
                self.adjust_sensitivity_auto()

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

        self.widgets_enabled_when_connected = []     #The widgets in this list will only be enabled when the interface has succesfully connected to a powermeter
        self.widgets_enabled_when_disconnected = []  #The widgets in this list will only be enabled when the interface is not connected to a powermeter
        
    def initialize(self):
        self.create_widgets()

        ### SET INITIAL STATE OF WIDGETS
        self.click_button_refresh_list_devices()    #By calling this method, as soon as the gui is created we also look for devices
        self.set_disconnected_state()               #When GUI is created, all widgets are set to the "Disconnected" state
        if self.interface.settings['sensitivity_auto']:
            self.box_SensitivityAuto.setChecked(True)
        ###

        self.connect_widgets_events_to_functions()

        ### Call the initialize method of the parent class
        super().initialize()

    def create_widgets(self):
        hbox1 = Qt.QHBoxLayout()
        self.label_DeviceList = Qt.QLabel("Devices: ")
        self.combo_Devices = Qt.QComboBox()
        self.button_RefreshDeviceList = Qt.QPushButton("")
        self.button_RefreshDeviceList.setIcon(QtGui.QIcon(path.join(graphics_dir,'refresh.png')))
        hbox1.addWidget(self.label_DeviceList)
        hbox1.addWidget(self.combo_Devices,stretch=1)
        hbox1.addWidget(self.button_RefreshDeviceList)

        hbox2 = Qt.QHBoxLayout()
        self.button_ConnectDevice = Qt.QPushButton("Connect")
        self.button_SetAutoScale = Qt.QPushButton("Set Auto Scale")
        self.label_TimeConstants = Qt.QLabel("Time constant (s): ")
        self.combo_TimeConstants = Qt.QComboBox()

        self.label_Sensitivities = Qt.QLabel("Sensitivity (V): ")
        self.combo_Sensitivities = Qt.QComboBox()

        self.box_SensitivityAuto = Qt.QCheckBox("Auto")
        self.box_SensitivityAuto.setToolTip('Enables a software-controlled adjustement of sensitivity.')

        hbox2.addWidget(self.button_ConnectDevice)
        hbox2.addWidget(self.button_SetAutoScale)
        hbox2.addWidget(self.label_TimeConstants)
        hbox2.addWidget(self.combo_TimeConstants,stretch=1)
        hbox2.addWidget(self.label_Sensitivities)
        hbox2.addWidget(self.combo_Sensitivities,stretch=1)
        hbox2.addWidget(self.box_SensitivityAuto)

        hbox3 = Qt.QHBoxLayout()
        hbox3_vbox1 = Qt.QVBoxLayout()
        
        self.button_StartPauseReading = Qt.QPushButton("")
        self.button_StartPauseReading.setIcon(QtGui.QIcon(path.join(graphics_dir,'play.png')))
        self.button_StartPauseReading.setToolTip('Start or pause the reading from the device. The previous data points are not discarded when pausing.') 
        #if plot:
        #    self.button_StopReading = Qt.QPushButton("")
        #    self.button_StopReading.setIcon(QtGui.QIcon(path.join(graphics_dir,'stop.png')))
        #    self.button_StopReading.setToolTip('Stop the reading from the device. All previous data points are discarded.') 
        #    self.button_StopReading.clicked.connect(self.click_button_StopReading)
        #else:
        #    self.button_StopReading = None
        hbox3_vbox1_hbox1 = Qt.QHBoxLayout()
        hbox3_vbox1_hbox1.addWidget(self.button_StartPauseReading)  
        #if plot:
        #    hbox3_vbox1_hbox1.addWidget(self.button_StopReading)
        
        self.label_RefreshTime = Qt.QLabel("Refresh time (s): ")
        self.label_RefreshTime.setToolTip('Specifies how often data is read from the device (Minimum value = 0.001 s).') 
        self.edit_RefreshTime  = Qt.QLineEdit()
        self.edit_RefreshTime.setText(f"{self.interface.settings['refresh_time']:.3f}")
        self.edit_RefreshTime.setToolTip('Specifies how often data is read from the device (Minimum value = 0.001 s).') 
        self.edit_RefreshTime.setAlignment(QtCore.Qt.AlignRight)
        hbox3_vbox1_hbox2 = Qt.QHBoxLayout()
        hbox3_vbox1_hbox2.addWidget(self.label_RefreshTime)  
        hbox3_vbox1_hbox2.addWidget(self.edit_RefreshTime,stretch=1)

        hbox3_vbox1.addLayout(hbox3_vbox1_hbox1)
        hbox3_vbox1.addLayout(hbox3_vbox1_hbox2)


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
        self.layout_ContainerOutputs.setSpacing(0)
        self.layout_ContainerOutputs.setContentsMargins(0, 0, 0, 0)
        self.widget_ContainerOutputs = Qt.QWidget()
        self.widget_ContainerOutputs.setLayout(self.layout_ContainerOutputs)

        hbox3.addLayout(hbox3_vbox1)
        hbox3.addWidget(self.widget_ContainerOutputs,stretch=1)
     
        self.container = Qt.QVBoxLayout()
        self.container.addLayout(hbox1)  
        self.container.addLayout(hbox2)  
        self.container.addLayout(hbox3)  
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
        
    def set_disconnected_state(self):
        self.disable_widget(self.widgets_enabled_when_connected)
        self.enable_widget(self.widgets_enabled_when_disconnected)
        self.button_ConnectDevice.setText("Connect")

    def set_connecting_state(self):
        self.disable_widget(self.widgets_enabled_when_connected)
        self.enable_widget(self.widgets_enabled_when_disconnected)
        self.button_ConnectDevice.setText("Connecting...")

    def set_connected_state(self):
        self.enable_widget(self.widgets_enabled_when_connected)
        self.disable_widget(self.widgets_enabled_when_disconnected)
        self.button_ConnectDevice.setText("Disconnect")

    def set_pause_state(self):
        self.button_StartPauseReading.setIcon(QtGui.QIcon(path.join(graphics_dir,'play.png')))
    def set_reading_state(self):
        self.button_StartPauseReading.setIcon(QtGui.QIcon(path.join(graphics_dir,'pause.png')))
    def set_stopped_state(self):    
        self.button_StartPauseReading.setIcon(QtGui.QIcon(path.join(graphics_dir,'play.png')))

############################################################
### GUI Events Functions
############################################################

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
        self.interface.set_sensitivty_auto(status_bool)
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
        if self.child:
            pass #self.child.close()

def main():
    parser = argparse.ArgumentParser(description = "",epilog = "")
    parser.add_argument("-s", "--decrease_verbose", help="Decrease verbosity.", action="store_true")
    args = parser.parse_args()

    app = Qt.QApplication(sys.argv)
    window = MainWindow()
    Interface = interface(app=app,mainwindow=window) #In this case window is both the MainWindow and the parent of the gui
    Interface.verbose = not(args.decrease_verbose)
    app.aboutToQuit.connect(Interface.close) 
    Interface.create_gui(window)
    window.show()
    app.exec()# Start the event loop.

if __name__ == '__main__':
    main()
