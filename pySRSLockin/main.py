''' Note: most of docstrings in this file have been generated automatically by Claude. AI can make mistakes'''
import os
import PyQt5
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname, 'plugins', 'platforms')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
import PyQt5.QtWidgets as Qt# QApplication, QWidget, QMainWindow, QPushButton, QHBoxLayout
import PyQt5.QtGui as QtGui
import PyQt5.QtCore as QtCore
import logging
import math
import sys
import time
import argparse

import abstract_instrument_interface
import pySRSLockin.driver 

graphics_dir = os.path.join(os.path.dirname(__file__), 'graphics')

##This application follows the model-view-controller paradigm, but with the view and controller defined inside the same object (the GUI)
##The model is defined by the class 'interface', and the view+controller is defined by the class 'gui'. 

class interface(abstract_instrument_interface.abstract_interface):
    """
    High-level model for SRS lock-in amplifiers, built on top of
    :class:`abstract_instrument_interface.abstract_interface`.

    Wraps a :class:`~pySRSLockin.driver.SRS_Lockin` driver instance, validates user input, periodically reads
    data from the device, and exposes its state via Qt signals. Follows the model-view-controller pattern: this
    class is the model, and :class:`gui` is the view/controller.

    Class-level attributes
    ----------------------
    output : dict
        Produced data, with keys ``'X'``, ``'Y'``, ``'mag'``, ``'theta'``, ``'aux1'``, ``'aux2'``. Defined also
        as class attribute, so that the data produced by this interface can be known without creating an object.

    Signals
    -------
    sig_list_devices_updated : pyqtSignal(list)
        Emitted when the list of available devices is refreshed. Carries the list of device name strings
        (``"<identity> --> <address>"``) shown in the GUI combo box.
    sig_refreshtime : pyqtSignal(float)
        Emitted when the refresh time changes. Carries the new value in seconds.
    sig_reading : pyqtSignal(int)
        Emitted when the reading status changes. Parameter is one of ``SIG_READING_START``,
        ``SIG_READING_PAUSE``, or ``SIG_READING_STOP``.
    sig_updated_data : pyqtSignal(object)
        Emitted each time new data are read. Carries the dictionary :attr:`output`.
    sig_read_available_time_constants : pyqtSignal(list)
        Emitted upon connection. Carries the list of time constants (s) available on the device.
    sig_read_available_sensitivities : pyqtSignal(list)
        Emitted upon connection. Carries the list of sensitivities (V) available on the device.
    sig_set_time_constant : pyqtSignal(int)
        Emitted after the time constant was successfully changed. Carries its index.
    sig_read_time_constant : pyqtSignal(list)
        Emitted after the time constant is read. Carries ``[index, value]``, with value in seconds.
    sig_set_sensitivity : pyqtSignal(int)
        Emitted after the sensitivity was successfully changed. Carries its index.
    sig_read_sensitivity : pyqtSignal(list)
        Emitted after the sensitivity is read. Carries ``[index, value]``, with value in volts.
    sig_sensitivity_auto_change : pyqtSignal(bool)
        Emitted when the software auto-sensitivity is turned on/off. Carries the new status.
    sig_data_to_read : pyqtSignal(str, bool)
        Emitted when an element of ``settings['data_to_read']`` changes. Carries the output name and the new status.
    sig_device_features : pyqtSignal(dict)
        Emitted upon connection. Carries ``{'outputs': list, 'auto_scale': bool, 'frequency_set': bool,
        'phase_set': bool}``: the outputs provided by the device, and whether it supports auto-scale and
        setting frequency and phase.
    sig_frequency : pyqtSignal(float)
        Emitted when the reference frequency is read and its value changed (or after it is set). Carries the frequency in Hz.
    sig_phase : pyqtSignal(float)
        Emitted when the reference phase is read and its value changed (or after it is set). Carries the phase in degrees.

    Status codes
    ------------
    SIG_READING_START : int (= 1)
        Reading has started (continuous acquisition is active).
    SIG_READING_PAUSE : int (= 2)
        Reading has been paused (accumulated data are preserved).
    SIG_READING_STOP : int (= 3)
        Reading has been stopped and all accumulated data cleared.

    Instance attributes
    -------------------
    instrument : SRS_Lockin
        The low-level driver instance used to communicate with the device.
    list_devices : list of [str, str, str]
        Devices found by the last scan, as ``[address, identity, model]``.
    connected_device_name : str
        VISA address of the currently connected device, or empty string if disconnected.
    continuous_read : bool
        When ``True``, :meth:`update` reads data continuously at the rate set by ``settings['refresh_time']``.
    stored_data : dict of lists
        Values accumulated since the last :meth:`stop_reading`, one list per output. Outputs that are not read
        in a given cycle are stored as ``nan``, so that all lists have the same length.
    supported_outputs : list of str
        Outputs provided by the connected device (e.g. ``['X', 'aux1', 'aux2']`` for the SR510).
    time_constants, sensitivities : list of float
        Time constants (s) and sensitivities (V) available on the connected device.
    time_constant, sensitivity : int or None
        Index of the current time constant and sensitivity in the lists above.
    frequency, phase : float or None
        Last reference frequency (Hz) and phase (deg) read from the device.
    refresh_time_reference : float
        Minimum time interval (s) between consecutive readings of frequency and phase during continuous reading.
    settings : dict
        ``'refresh_time'`` (float, s), ``'sensitivity_auto'`` (bool, software auto-sensitivity on/off) and
        ``'data_to_read'`` (dict ``{output_name: bool}``, outputs to read continuously). Saved into
        ``config.json`` when the interface is closed.
    """
    output = {'X':0,'Y':0,'mag':0,'theta':0,'aux1':0,'aux2':0}  #We define this also as class variable. This makes it possible to see which data is produced by this interface without having to create an object


    ## SIGNALS THAT WILL BE USED TO COMMUNICATE WITH THE GUI
    #                                                                   | Triggered when ...                                                            | Parameter(s) Sent  
    #                                                               #   -----------------------------------------------------------------------------------------------------------------------         
    sig_list_devices_updated = QtCore.pyqtSignal(list)              #   | List of devices is updated                                                    | List of devices   
    sig_refreshtime = QtCore.pyqtSignal(float)                      #   | Refresh time is changed                                                       | New value of refresh time
    sig_reading = QtCore.pyqtSignal(int)                            #   | Reading status changes                                                        | 1 = Started Reading, 2 = Paused Reading, 3 Stopped Reading 
    sig_updated_data = QtCore.pyqtSignal(object)                    #   | Data is read from instrument                                                  | Acquired data 
    sig_read_available_time_constants = QtCore.pyqtSignal(list)     #
    sig_read_available_sensitivities = QtCore.pyqtSignal(list)      #
    sig_set_time_constant = QtCore.pyqtSignal(int)                  #
    sig_read_time_constant = QtCore.pyqtSignal(list)                #list of two integers, first is integer index of time constant, second is numerical value of time constant
    sig_set_sensitivity = QtCore.pyqtSignal(int)                    #list of two integers, first is integer index of sensitivity, second is numerical value of sensitivity
    sig_read_sensitivity = QtCore.pyqtSignal(list)                  #list of two integers, first is integer index of sensitivity, second is numerical value of sensitivity
    sig_sensitivity_auto_change = QtCore.pyqtSignal(bool) 
    sig_data_to_read = QtCore.pyqtSignal(str,bool)                  #   | The status of one of the elements of self.settings['data_to_read'] is changed  | Key of the element changed, new value of the element
    sig_device_features = QtCore.pyqtSignal(dict)                   #   | A device is connected                                                         | {'outputs': list, 'auto_scale': bool, 'frequency_set': bool, 'phase_set': bool}
    sig_frequency = QtCore.pyqtSignal(float)                        #   | Reference frequency is read from the device                                   | Frequency (Hz)
    sig_phase = QtCore.pyqtSignal(float)                            #   | Reference phase is read from the device                                       | Phase (deg)
    ##
    # Identifier codes used for view-model communication. Other general-purpose codes are specified in abstract_instrument_interface
    SIG_READING_START = 1
    SIG_READING_PAUSE = 2
    SIG_READING_STOP = 3

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        **kwargs
            Forwarded to :class:`~abstract_instrument_interface.abstract_interface`. Required key: ``app``
            (``Qt.QApplication``). Optional keys include ``name_logger`` (str) and ``config_dict`` (dict).
        """
        self.output = {'X':0,'Y':0,'mag':0,'theta':0,'aux1':0,'aux2':0} 
        ### Default values of settings (might be overlapped by settings saved in .json files later)
        self.settings = {   'refresh_time': 0.2,        #default refresh rate, in seconds
                            'sensitivity_auto': True,    #Boolean, true if software-controlled automatic sensitivity is enabled
                            'data_to_read': {'X':0,'Y':0,'mag':1,'theta':0,'aux1':0,'aux2':0}
                            }

        self.list_devices = []          #list of devices found
        self.continuous_read = False #When this is set to True, the data from device are acquired continuosly at the rate set by self.settings['refresh_time']
        self.stored_data = {'X':[],'Y':[],'mag':[],'theta':[],'aux1':[],'aux2':[]}  # List used to store recorded data
        self.connected_device_name = ''
        self.supported_outputs = list(self.output.keys())  #Outputs supported by the connected device (updated upon connection)
        self.frequency = None               #Last value of reference frequency (Hz) read from the device
        self.phase = None                   #Last value of reference phase (deg) read from the device
        self.refresh_time_reference = 1     #Minimum time interval (s) between consecutive readings of frequency and phase during continuous reading
        self._last_reference_read = 0
        
        self.instrument = pySRSLockin.driver.SRS_Lockin() 
  
        super().__init__(**kwargs)
        self.refresh_list_devices()   

############################################################
### Functions to interface the GUI and low-level driver
############################################################

    def refresh_list_devices(self):
        """
        Scan for available devices using the driver, update :attr:`list_devices`, and emit
        :attr:`sig_list_devices_updated` to refresh the GUI combo box.
        """
        self.logger.info(f"Looking for devices...") 
        list_valid_devices = self.instrument.list_devices()
        self.logger.info(f"Found {len(list_valid_devices)} devices.")
        self.list_devices = list_valid_devices
        self.send_list_devices()

    def send_list_devices(self):
        """
        Emit :attr:`sig_list_devices_updated` with the current device list formatted as
        ``"<identity> --> <address>"`` strings, ready to populate the GUI combo box.
        If no devices are found, an empty list is emitted.
        """
        if(len(self.list_devices)>0):
            list_IDNs_and_devices = [dev[1] + " --> " + dev[0] for dev in self.list_devices] 
        else:
            list_IDNs_and_devices = []
        self.sig_list_devices_updated.emit(list_IDNs_and_devices)

    def connect_device(self,device_full_name):
        """
        Connect to the device identified by ``device_full_name``.

        Parameters
        ----------
        device_full_name : str
            A string of the form ``"<identity> --> <address>"``, as produced by :meth:`send_list_devices` and
            displayed in the GUI combo box. The VISA address is extracted from the part after ``" --> "``.
            If empty, an error is logged and the method returns immediately.

        Notes
        -----
        On success, calls :meth:`set_connected_state`, which reads the device features, time constant and
        sensitivity, and starts continuous reading. On failure, calls :meth:`set_disconnected_state` and logs an error.
        """
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
        """
        Disconnect the currently connected device.

        Continuous reading is stopped first, so that no pending :meth:`update` tries to read from a closed device.
        If disconnection fails (e.g. the device was already physically unplugged), the disconnected state is still
        set, so that the GUI resets correctly.
        """
        self.logger.info(f"Disconnecting from device {self.connected_device_name}...")
        self.continuous_read = False # Stop the continuous reading before disconnecting, so that no pending update() tries to read from a closed device
        (Msg,ID) = self.instrument.disconnect_device()
        if(ID==1): # If disconnection was successful
            self.logger.info(f"Disconnected from device {self.connected_device_name}.")
            self.set_disconnected_state()
        else: #If disconnection was not successful
            self.logger.error(f"Error: {Msg}")
            self.set_disconnected_state() #When disconnection is not succeful, it is typically because the device alredy lost connection
                                        #for some reason. In this case, it is still useful to have all widgets reset to disconnected state    
    
    def close(self,**kwargs):
        """
        Close this interface. Delegates to the parent class
        :meth:`~abstract_instrument_interface.abstract_interface.close`, which emits ``sig_close``, saves the
        settings into ``config.json``, and disconnects the device if connected.
        """
        super().close(**kwargs)         

    def fire_all_signals(self):
        """
        Emit all signals carrying the current settings (device list, refresh time, outputs to read, software
        auto-sensitivity status). Typically called by the GUI after its widgets are created, so that they can be
        populated with the current values.
        """
        self.send_list_devices()
        self.sig_refreshtime.emit(self.settings['refresh_time'])
        for data_name in self.output.keys():
            self.sig_data_to_read.emit(data_name,self.settings['data_to_read'][data_name])    
        self.sig_sensitivity_auto_change.emit(self.settings['sensitivity_auto'])

    def set_connected_state(self):
        """
        Extend the parent :meth:`~abstract_instrument_interface.abstract_interface.set_connected_state` to
        perform the initialization specific to lock-in amplifiers after a successful connection: read the device
        features (:meth:`read_device_features`), the available and current time constants and sensitivities, and
        start continuous reading.
        """
        super().set_connected_state()
        self.read_device_features()
        self.read_available_time_constants()
        self.read_available_sensitivities()
        self.read_time_constant()
        self.read_sensitivity()
        self.start_reading()

    def read_device_features(self):
        """
        Read which outputs (X, Y, mag, ...) and functions are supported by the connected device (e.g. the SR510
        only measures X, has no auto-scale, and its frequency cannot be set), and notify the GUI via
        :attr:`sig_device_features`. Unsupported outputs are set to ``nan`` in :attr:`output`. Frequency and phase
        are then read and sent to the GUI.
        """
        self.supported_outputs = self.instrument.supported_outputs
        auto_scale = self.instrument.supports_property('auto_sensitivity')
        unsupported = [k for k in self.output.keys() if k not in self.supported_outputs]
        for k in unsupported:
            self.output[k] = math.nan
        if unsupported:
            self.logger.info(f"Model {self.instrument.model} does not support: {', '.join(unsupported)}.")
        self.sig_device_features.emit({'outputs': list(self.supported_outputs), 'auto_scale': auto_scale,
                                       'frequency_set': self.instrument.supports_property('frequency_SET'),
                                       'phase_set': self.instrument.supports_property('phase_SET')})
        self.read_frequency(force_emit=True)
        self.read_phase(force_emit=True)

    def read_frequency(self, force_emit=False):
        """
        Read the reference frequency from the device and store it in :attr:`frequency`.

        Parameters
        ----------
        force_emit : bool, optional
            If ``False`` (default), :attr:`sig_frequency` is emitted only if the value changed since the last
            reading. If ``True``, it is always emitted.

        Returns
        -------
        float or None
            The frequency (Hz), or ``None`` if an error occurred (the error is logged).
        """
        try:
            f = self.instrument.frequency
        except Exception as e:
            self.logger.error(f"An error occurred while reading the frequency: {e}")
            return None
        if force_emit or f != self.frequency:
            self.sig_frequency.emit(f)
        self.frequency = f
        return f

    def read_phase(self, force_emit=False):
        """
        Read the reference phase from the device and store it in :attr:`phase`.

        Parameters
        ----------
        force_emit : bool, optional
            If ``False`` (default), :attr:`sig_phase` is emitted only if the value changed since the last
            reading. If ``True``, it is always emitted.

        Returns
        -------
        float or None
            The phase (deg), or ``None`` if an error occurred (the error is logged).
        """
        try:
            p = self.instrument.phase
        except Exception as e:
            self.logger.error(f"An error occurred while reading the phase: {e}")
            return None
        if force_emit or p != self.phase:
            self.sig_phase.emit(p)
        self.phase = p
        return p

    def set_frequency(self, frequency):
        """
        Set the reference frequency, then read it back and emit :attr:`sig_frequency`.

        Setting the frequency is only effective when the device uses its internal reference, and it is not
        possible on the SR510. If the value read back differs by more than 0.1% from the requested one, an
        error is logged.

        Parameters
        ----------
        frequency : float or str
            New frequency (Hz). Must be convertible to a positive float.

        Returns
        -------
        bool
            ``True`` if the frequency was set successfully, ``False`` otherwise (the reason is logged, and the
            GUI is updated with the current value).
        """
        try:
            frequency = float(frequency)
            if not (frequency > 0):
                raise ValueError
        except ValueError:
            self.logger.error(f"The frequency must be a positive number.")
            self.read_frequency(force_emit=True) #restore the displayed value
            return False
        if not self.instrument.supports_property('frequency_SET'):
            self.logger.error(f"Model {self.instrument.model} does not allow setting the frequency.")
            self.read_frequency(force_emit=True)
            return False
        self.logger.info(f"Setting frequency to {frequency} Hz...")
        try:
            self.instrument.frequency = frequency
        except Exception as e:
            self.logger.error(f"An error occurred while setting the frequency: {e}")
            self.read_frequency(force_emit=True)
            return False
        f_new = self.read_frequency(force_emit=True)
        if f_new is None:
            return False
        if abs(f_new - frequency) > 1e-3 * frequency:
            self.logger.error(f"The frequency is now {f_new} Hz, instead of {frequency} Hz. The device might be using an external reference, or the value is out of range.")
            return False
        self.logger.info(f"Frequency is now {f_new} Hz.")
        return True

    def step_phase(self, delta):
        """
        Change the reference phase by ``delta``. The current phase is read from the device, and the new value is
        wrapped into the range [-180, 180) deg.

        Parameters
        ----------
        delta : float
            Phase change (deg), e.g. ``+1`` or ``-10``.

        Returns
        -------
        bool
            ``True`` if the phase was set successfully, ``False`` otherwise.
        """
        p = self.read_phase()
        if p is None:
            return False
        return self.set_phase(round((p + float(delta) + 180) % 360 - 180, 6))  #round() removes floating-point noise (e.g. 56.099999999999994)

    def set_phase(self, phase):
        """
        Set the reference phase, then read it back and emit :attr:`sig_phase`. The device may wrap the value
        into its own range (e.g. 270 -> -90 deg).

        Parameters
        ----------
        phase : float or str
            New phase (deg). Must be convertible to float.

        Returns
        -------
        bool
            ``True`` if the phase was set successfully, ``False`` otherwise (the reason is logged, and the
            GUI is updated with the current value).
        """
        try:
            phase = float(phase)
        except ValueError:
            self.logger.error(f"The phase must be a valid number.")
            self.read_phase(force_emit=True)
            return False
        if not self.instrument.supports_property('phase_SET'):
            self.logger.error(f"Model {self.instrument.model} does not allow setting the phase.")
            self.read_phase(force_emit=True)
            return False
        self.logger.info(f"Setting phase to {phase} deg...")
        try:
            self.instrument.phase = phase
        except Exception as e:
            self.logger.error(f"An error occurred while setting the phase: {e}")
            self.read_phase(force_emit=True)
            return False
        p_new = self.read_phase(force_emit=True)
        if p_new is None:
            return False
        self.logger.info(f"Phase is now {p_new} deg.")  #The device may wrap the value (e.g. 270 -> -90)
        return True

    def set_data_to_read(self,data_name,acquire):
        """
        Select whether an output is read continuously, and emit :attr:`sig_data_to_read`.

        Parameters
        ----------
        data_name : str
            Name of the output, i.e. one of the keys of :attr:`output`. Other values are ignored.
        acquire : bool
            If ``True``, this output is read at every cycle of :meth:`update`.

        Returns
        -------
        bool or None
            ``False`` if ``acquire`` cannot be converted to bool, ``None`` otherwise.
        """
        try:
            acquire = bool(acquire)
        except ValueError:
            self.logger.error(f"The input argument acquire must be a boolean (or convertible to boolean)")
            return False
        if data_name in self.output.keys():
            self.settings['data_to_read'][data_name] = acquire
            self.sig_data_to_read.emit(data_name,self.settings['data_to_read'][data_name])

    def set_refresh_time(self, refresh_time):
        """
        Set the time interval between consecutive readings, and emit :attr:`sig_refreshtime`.

        Parameters
        ----------
        refresh_time : float or str
            New refresh time (s). Must be a number >= 0.001.

        Returns
        -------
        bool
            ``True`` if the refresh time is valid (and was set), ``False`` otherwise (the error is logged, and the
            previous value is sent back to the GUI).
        """
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
        """
        Read the list of time constants available on the device, store it in :attr:`time_constants`, and emit
        :attr:`sig_read_available_time_constants`.
        """
        self.logger.info(f"Reading all possible values of time constants from device...")
        self.time_constants = self.instrument.time_constants
        self.logger.info(f"This device supports {len(self.time_constants)} different time constants.") 
        self.sig_read_available_time_constants.emit(self.time_constants)

    def read_available_sensitivities(self):
        """
        Read the list of sensitivities available on the device, store it in :attr:`sensitivities`, and emit
        :attr:`sig_read_available_sensitivities`.
        """
        self.logger.info(f"Reading all possible values of sensitivities from device...")
        self.sensitivities = self.instrument.sensitivities
        self.logger.info(f"This device supports {len(self.sensitivities)} different sensitivities.") 
        self.sig_read_available_sensitivities.emit(self.sensitivities)

    def read_time_constant(self):
        """
        Read the current time constant from the device, store its index in :attr:`time_constant`, and emit
        :attr:`sig_read_time_constant`. If the reading fails, an error is logged.
        """
        self.logger.info(f"Reading current time constant from device {self.connected_device_name}...") 
        self.time_constant = self.instrument.time_constant
        if self.time_constant == None:
            self.logger.error(f"An error occurred while reading the time constant from this device.")
            return
        
        self.sig_read_time_constant.emit([self.time_constant,self.time_constants[self.time_constant]])
        self.logger.info(f"Current time constant is {self.time_constants[self.time_constant]} (index={self.time_constant})...") 

    def read_sensitivity(self, log= True):
        """
        Read the current sensitivity from the device, store its index in :attr:`sensitivity`, and emit
        :attr:`sig_read_sensitivity`. If the reading fails, an error is logged.

        Parameters
        ----------
        log : bool, optional
            If ``False``, the informative log messages are not produced. Useful to avoid filling the logs when the
            sensitivity is changed very often (e.g. by the software auto-sensitivity). Default is ``True``.
        """
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
        """
        Set the time constant, read it back to confirm the change, and emit :attr:`sig_set_time_constant`.

        Parameters
        ----------
        tc : int
            Index of the new time constant in :attr:`time_constants`.

        Returns
        -------
        bool or None
            ``None`` if ``tc`` is equal to the current index (nothing is done), ``False`` if an error occurred,
            ``True`` otherwise.
        """
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
        """
        Set the sensitivity, read it back to confirm the change, and emit :attr:`sig_set_sensitivity`.

        Parameters
        ----------
        s : int
            Index of the new sensitivity in :attr:`sensitivities`.
        log : bool, optional
            If ``False``, the informative log messages are not produced. Default is ``True``.

        Returns
        -------
        bool or None
            ``None`` if ``s`` is equal to the current index (nothing is done), ``False`` if an error occurred,
            ``True`` otherwise.
        """
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
        """
        Run the auto-gain / auto-scale function of the instrument (not available on the SR510), and log the result.
        """
        ID = self.instrument.set_auto_scale()
        if ID==0:
            self.logger.error(f"It was not possible to set 'auto scale'. This device model might not support it.")
        else:
            self.logger.info(f"'auto scale' set correctly.")

    def set_sensitivity_auto(self,status):
        """
        Turn on/off the software-controlled automatic sensitivity (see :meth:`adjust_sensitivity_auto`), and emit
        :attr:`sig_sensitivity_auto_change`.

        Parameters
        ----------
        status : bool
            ``True`` to turn the software auto-sensitivity on.
        """
        self.settings['sensitivity_auto'] = status
        if status==True:
            self.logger.info(f"Auto-adjustement sensitivity (via software) set to ON.")
            if self.instrument.connected == True:
                self.read_sensitivity() #make sure to read the current value of sensitivity
        else:
            self.logger.info(f"Auto-adjustement sensitivity (via software) set to OFF.")
        self.sig_sensitivity_auto_change.emit(self.settings['sensitivity_auto'])

    def output_for_auto_sensitivity(self):
        """
        Return the name of the output used by the software auto-sensitivity.

        Returns
        -------
        str
            ``'mag'`` if the connected device provides it, ``'X'`` otherwise (e.g. SR510, where ``|X|`` is used).
        """
        return 'mag' if 'mag' in self.supported_outputs else 'X'

    def adjust_sensitivity_auto(self, current_mag):
        """
        Adjust the sensitivity of the instrument based on the current signal amplitude.

        If the amplitude is between 20% and 80% of the current full-scale sensitivity, nothing is done.
        Otherwise, the sensitivity is set to the smallest available value larger than ``amplitude/0.8``
        (or to the largest available value, if none is large enough).

        Parameters
        ----------
        current_mag : float
            Current signal amplitude (V). Its absolute value is used. If ``nan``, nothing is done.

        Returns
        -------
        bool or None
            ``False`` if the sensitivity was not changed, otherwise the result of :meth:`set_sensitivity`.
        """
        max_bound = 0.8
        min_bound = 0.2
        current_mag = abs(current_mag)
        if self.sensitivity is None or math.isnan(current_mag):
            return False
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
        """
        Start continuous reading from the device: emit :attr:`sig_reading` with ``SIG_READING_START``, set
        :attr:`continuous_read` to ``True`` and call :meth:`update`. If no device is connected, an error is logged.
        """
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
        """
        Pause continuous reading (accumulated data in :attr:`stored_data` are preserved), and emit
        :attr:`sig_reading` with ``SIG_READING_PAUSE``.
        """
        self.continuous_read = False
        self.logger.info(f"Paused reading from device {self.connected_device_name}.")
        self.sig_reading.emit(self.SIG_READING_PAUSE) # This signal will be caught by the GUI
        return

    def stop_reading(self):
        """
        Stop continuous reading, delete all accumulated data in :attr:`stored_data`, and emit :attr:`sig_reading`
        with ``SIG_READING_STOP``.
        """
        self.continuous_read = False
        self.stored_data = {k:[] for k in self.output.keys()}
        self.update() #We call one more time the self.update() function to make sure plots is cleared. Since self.continuous_read is already set to False, update() will not acquire data anymore
        self.logger.info(f"Stopped reading from device {self.connected_device_name}. All stored data have been deleted.")
        self.sig_reading.emit(self.SIG_READING_STOP) # This signal will be caught by the GUI
        # ...
        return
        
    def update(self):
        """
        Read data from the device and schedule the next reading. Does nothing if :attr:`continuous_read` is ``False``.

        At each call:

        1. The outputs selected in ``settings['data_to_read']`` and supported by the device are read in a single
           call to :meth:`~pySRSLockin.driver.SRS_Lockin.read_outputs` (simultaneously, when the model supports it).
           If the software auto-sensitivity is on, the output used for it is read as well. Outputs not read are set
           to ``nan``. Values are stored in :attr:`output` and appended to :attr:`stored_data`.
        2. :meth:`~abstract_instrument_interface.abstract_interface.update` of the parent class is called (it sends
           a trigger, if one was set).
        3. Frequency and phase are read, at most once every :attr:`refresh_time_reference` seconds.
        4. If enabled, the sensitivity is adjusted (:meth:`adjust_sensitivity_auto`).
        5. :attr:`sig_updated_data` is emitted, and the next call is scheduled after ``settings['refresh_time']`` seconds.

        If reading fails, the error is logged and reading is paused.
        """
        #self.plot_object.data.setData(list(range(1, len(self.stored_powers)+1)), self.stored_powers) #This line is executed even when self.continuous_read == False, to make sure that plot gets cleared when user press the stop button
        if(self.continuous_read == True):
            #Outputs to read: those selected by the user and supported by the device. If the software auto-sensitivity is on,
            #the output used for it is read too (even if not selected)
            to_read = [k for k in self.output.keys() if self.settings['data_to_read'][k] and k in self.supported_outputs]
            ref = self.output_for_auto_sensitivity()
            to_read_all = to_read + [ref] if (self.settings['sensitivity_auto'] and ref not in to_read) else to_read
            try:
                values = self.instrument.read_outputs(to_read_all) if to_read_all else {}  #simultaneous reading, when supported by the device
            except Exception as e:
                self.logger.error(f"An error occurred while reading from the device: {e}")
                self.pause_reading()
                return
            for k in self.output.keys(): #Outputs not read in this cycle are set to nan, so that stored data are not mixed with old values
                self.output[k] = values[k] if k in to_read else math.nan
            for k in self.output.keys():	
                self.stored_data[k].append(self.output[k])

            super().update()

            #Frequency and phase are read at most once every self.refresh_time_reference seconds
            if time.monotonic() - self._last_reference_read >= self.refresh_time_reference:
                self._last_reference_read = time.monotonic()
                self.read_frequency()  #the GUI is notified only if the value changed
                self.read_phase()

            if self.settings['sensitivity_auto'] == True:
                self.adjust_sensitivity_auto(values[ref])

            self.sig_updated_data.emit(self.output)
            QtCore.QTimer.singleShot(int(self.settings['refresh_time']*1e3), self.update)
           
        return

############################################################
### END Functions to interface the GUI and low-level driver
############################################################

class gui(abstract_instrument_interface.abstract_gui):
    """
    PyQt5 view/controller for the SRS lock-in interface.

    Inherits from :class:`~abstract_instrument_interface.abstract_gui`. Builds the instrument panel
    (connection row; refresh time, auto scale, time constant and sensitivity row; frequency and phase row;
    start/pause button and output boxes), wires widget events to :class:`interface` methods, and connects
    :class:`interface` signals to event slots that update the widgets.

    Instance attributes
    -------------------
    checkbox_Output, edit_Output : dict
        Checkbox (select whether to read) and read-only text box (value) for each output, with the output
        names as keys.
    buttons_PhaseStep : dict
        Buttons that change the phase by -10, -1, +1 and +10 deg, with the step as key.
    widgets_enabled_when_connected : list of Qt.QWidget
        Widgets enabled only while a device is connected.
    widgets_enabled_when_disconnected : list of Qt.QWidget
        Widgets enabled only while no device is connected (device combo box and refresh button).
    """
    def __init__(self,interface,parent):
        """
        Parameters
        ----------
        interface : interface
            The :class:`interface` (model) object controlled by this GUI.
        parent : Qt.QWidget
            The Qt widget that will host this GUI panel.
        """
        super().__init__(interface,parent)
        self.initialize()

    def initialize(self):
        """
        Create the widgets, connect widget events to their handlers, call the parent
        :meth:`~abstract_instrument_interface.abstract_gui.initialize` (which sets the layout of the parent
        widget), connect the interface signals to the event slots, and ask the interface to emit all its signals
        so that the widgets are populated. The widgets are initially set to the disconnected state.
        """
        self.create_widgets()
        self.connect_widgets_events_to_functions()

        ### Call the initialize method of the parent class
        super().initialize()

        ### Connect signals from model to event slots of this GUI
        self.interface.sig_list_devices_updated.connect(self.on_list_devices_updated)
        self.interface.sig_connected.connect(self.on_connection_status_change) 
        self.interface.sig_reading.connect(self.on_reading_status_change) 
        self.interface.sig_data_to_read.connect(self.on_data_to_read_change) 
        self.interface.sig_device_features.connect(self.on_device_features_change) 
        self.interface.sig_frequency.connect(self.on_frequency_change) 
        self.interface.sig_phase.connect(self.on_phase_change) 
        self.interface.sig_updated_data.connect(self.on_data_change) 
        self.interface.sig_sensitivity_auto_change.connect(self.on_sensitivity_auto_change) 
        self.interface.sig_read_available_time_constants.connect(self.on_list_time_constants_change)
        self.interface.sig_read_available_sensitivities.connect(self.on_list_sensitivities_change)
        self.interface.sig_read_time_constant.connect(self.on_time_constant_change)
        self.interface.sig_read_sensitivity.connect(self.on_sensitivity_change)
        self.interface.sig_refreshtime.connect(self.on_refreshtime_change)
        self.interface.sig_close.connect(self.on_close)

        ### SET INITIAL STATE OF WIDGETS
        #self.edit_RefreshTime.setText(f"{self.interface.settings['refresh_time']:.3f}")
        self.interface.fire_all_signals()
        self.on_connection_status_change(self.interface.SIG_DISCONNECTED) #When GUI is created, all widgets are set to the "Disconnected" state    
        ###

    def create_widgets(self):
        """
        Create all widgets and layouts of the GUI, and store the main layout in ``self.container``.
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

        hbox_reference = Qt.QHBoxLayout()
        self.label_Frequency = Qt.QLabel("Frequency (Hz): ")
        self.edit_Frequency = Qt.QLineEdit()
        self.edit_Frequency.setAlignment(QtCore.Qt.AlignRight)
        self.label_Phase = Qt.QLabel("Phase (deg): ")
        self.edit_Phase = Qt.QLineEdit()
        self.edit_Phase.setAlignment(QtCore.Qt.AlignRight)
        self.buttons_PhaseStep = dict()
        for delta in [-10, -1, +1, +10]:
            b = Qt.QPushButton(f"{delta:+d}")
            b.setToolTip(f"Change the phase by {delta:+d} deg.")
            b.setMaximumWidth(40)
            self.buttons_PhaseStep[delta] = b
        for w in [self.label_Frequency, self.edit_Frequency, self.label_Phase,
                  self.buttons_PhaseStep[-10], self.buttons_PhaseStep[-1], self.edit_Phase, self.buttons_PhaseStep[+1], self.buttons_PhaseStep[+10]]:
            hbox_reference.addWidget(w)
        hbox_reference.addStretch(1)

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
        self.checkbox_Output = dict() 
        self.edit_Output = dict() 
        self.widget_Output = dict()     
        for k in self.interface.output.keys():	#Create display textbox for each of the output data of this interface	
            #self.label_Output[k] = Qt.QLabel(f"{k}: ")
            #self.label_Output[k].setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignCenter)
            #self.label_Output[k].setFont(fontLabel)
            self.checkbox_Output[k] = Qt.QCheckBox(f"{k}: ")
            #self.checkbox_Output[k].setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignCenter)
            self.checkbox_Output[k].setFont(fontLabel)
            self.edit_Output[k] = Qt.QLineEdit()
            self.edit_Output[k].setFont(fontEdit)
            self.edit_Output[k].setMinimumWidth(60)
            self.edit_Output[k].setAlignment(QtCore.Qt.AlignRight)
            self.edit_Output[k].setReadOnly(True)
            hbox_temp = Qt.QHBoxLayout()
            #hbox_temp.addWidget(self.label_Output[k])
            hbox_temp.addWidget(self.checkbox_Output[k])
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
     
        for box in [hbox1,hbox2,hbox_reference,hbox3]:
            self.container.addLayout(box)  
        self.container.addStretch(1)

        self.widgets_enabled_when_connected = [self.button_SetAutoScale, 
                                               self.combo_TimeConstants , 
                                               self.label_Sensitivities,
                                               self.combo_Sensitivities,
                                               self.button_StartPauseReading,
                                               #self.button_StopReading,
                                               self.box_SensitivityAuto,
                                               self.label_Frequency, self.edit_Frequency,
                                               self.label_Phase, self.edit_Phase] + list(self.buttons_PhaseStep.values())

        self.widgets_enabled_when_disconnected = [self.combo_Devices , 
                                                  self.button_RefreshDeviceList]
    
    def connect_widgets_events_to_functions(self):
        """
        Connect the events of the widgets (clicks, Enter key, selections) to the corresponding handlers.
        """
        self.button_RefreshDeviceList.clicked.connect(self.click_button_refresh_list_devices)
        self.button_ConnectDevice.clicked.connect(self.click_button_connect_disconnect)
        self.button_SetAutoScale.clicked.connect(self.click_button_set_auto_scale)
        self.combo_TimeConstants.activated.connect(self.click_combo_time_constants)
        self.combo_Sensitivities.activated.connect(self.click_combo_sensitivities)
        self.box_SensitivityAuto.stateChanged.connect(self.click_box_SensitivityAuto)
        self.button_StartPauseReading.clicked.connect(self.click_button_StartPauseReading)
        self.edit_RefreshTime.returnPressed.connect(self.press_enter_refresh_time)
        self.edit_Frequency.returnPressed.connect(self.press_enter_frequency)
        self.edit_Phase.returnPressed.connect(self.press_enter_phase)
        for delta, b in self.buttons_PhaseStep.items():
            b.clicked.connect(lambda checked, d=delta: self.click_button_phase_step(d))
        for key in self.checkbox_Output.keys():
            self.checkbox_Output[key].stateChanged.connect(lambda state, x=key: self.click_box_data_to_change(x,state))

###########################################################################################################
### Event Slots. They are normally triggered by signals from the model, and change the GUI accordingly  ###
###########################################################################################################

    def on_connection_status_change(self,status):
        """
        Enable/disable widgets and update the text of the connect button, according to the connection status.

        Parameters
        ----------
        status : int
            One of ``SIG_CONNECTED``, ``SIG_CONNECTING``, ``SIG_DISCONNECTED``, ``SIG_DISCONNECTING`` (defined
            in :class:`~abstract_instrument_interface.abstract_interface`). On disconnection, the checkboxes of all
            outputs are enabled again.
        """
        if status == self.interface.SIG_DISCONNECTED:
            self.disable_widget(self.widgets_enabled_when_connected)
            self.enable_widget(self.widgets_enabled_when_disconnected)
            self.button_ConnectDevice.setText("Connect")
            for k in self.checkbox_Output.keys(): #Re-enable all outputs (some might have been disabled for the previous device)
                self.checkbox_Output[k].setEnabled(True)
                self.edit_Output[k].setEnabled(self.checkbox_Output[k].isChecked())
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
        """
        Update the icon of the start/pause button.

        Parameters
        ----------
        status : int
            One of ``SIG_READING_START``, ``SIG_READING_PAUSE``, ``SIG_READING_STOP``.
        """
        if status == self.interface.SIG_READING_PAUSE:
            self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'play.png')))
        if status == self.interface.SIG_READING_START:
            self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'pause.png')))
        if status == self.interface.SIG_READING_STOP: 
            self.button_StartPauseReading.setIcon(QtGui.QIcon(os.path.join(graphics_dir,'play.png')))

    def on_list_devices_updated(self,list_devices):
        """
        Fill the device combo box.

        Parameters
        ----------
        list_devices : list of str
            Device names, as ``"<identity> --> <address>"``.
        """
        self.combo_Devices.clear()  #First we empty the combobox  
        self.combo_Devices.addItems(list_devices) 

    def on_device_features_change(self,features):
        """
        Adapt the GUI to the features of the connected device: disable the checkboxes of outputs not provided by
        the device (their text boxes show "n/a"), disable the auto-scale button if not supported, make the
        frequency and phase boxes read-only and disable the phase-step buttons if they cannot be set.

        Parameters
        ----------
        features : dict
            ``{'outputs': list, 'auto_scale': bool, 'frequency_set': bool, 'phase_set': bool}``, as emitted by
            :attr:`interface.sig_device_features`.
        """
        for k in self.checkbox_Output.keys():
            supported = k in features['outputs']
            self.checkbox_Output[k].setEnabled(supported)
            self.edit_Output[k].setEnabled(supported and self.checkbox_Output[k].isChecked())
            if not supported:
                self.edit_Output[k].setText("n/a")
        self.button_SetAutoScale.setEnabled(features['auto_scale'])
        if not features['auto_scale']:
            self.button_SetAutoScale.setToolTip("Not supported by this device.")
        else:
            self.button_SetAutoScale.setToolTip("")
        #Frequency and phase are always shown; they are editable only if the device allows setting them
        for edit, settable, name in [(self.edit_Frequency, features['frequency_set'], 'frequency'), (self.edit_Phase, features['phase_set'], 'phase')]:
            edit.setReadOnly(not settable)
            if settable:
                edit.setToolTip(f"Type a new {name} and press Enter to set it." + (" Only effective with the internal reference." if name == 'frequency' else ""))
            else:
                edit.setToolTip(f"This device does not allow setting the {name} remotely.")
        for b in self.buttons_PhaseStep.values():
            b.setEnabled(features['phase_set'])

    def on_frequency_change(self,value):
        """
        Show a new frequency value, unless the user is typing in the frequency box.

        Parameters
        ----------
        value : float
            Frequency (Hz).
        """
        if not self.edit_Frequency.isModified(): #Do not overwrite a value that the user is typing
            self.edit_Frequency.setText(f"{value:.6g}")

    def on_phase_change(self,value):
        """
        Show a new phase value, unless the user is typing in the phase box.

        Parameters
        ----------
        value : float
            Phase (deg).
        """
        if not self.edit_Phase.isModified():
            self.edit_Phase.setText(f"{value:.2f}")

    def on_data_to_read_change(self,data,value):
        """
        Update the checkbox and text box of an output when its reading status changes.

        Parameters
        ----------
        data : str
            Output name.
        value : bool
            ``True`` if the output is read continuously.
        """
        self.checkbox_Output[data].setChecked(value)
        self.edit_Output[data].setEnabled(value)

    def on_data_change(self,data):
        """
        Show new output values in the text boxes. Outputs not provided by the device are skipped.

        Parameters
        ----------
        data : dict
            ``{output_name: value}``, as emitted by :attr:`interface.sig_updated_data`.
        """
        for k in data.keys():
            if not self.checkbox_Output[k].isEnabled(): #Output not supported by this device
                continue
            try:
                self.edit_Output[k].setText(f"{data[k]:.2e}")
            except:
                self.edit_Output[k].setText(f"nan")

    def on_list_time_constants_change(self,time_constants):
        """
        Fill the time-constant combo box.

        Parameters
        ----------
        time_constants : list of float
            Available time constants (s).
        """
        self.combo_TimeConstants.clear() #First we empty the combobox
        if len(time_constants)>0:
            self.combo_TimeConstants.addItems([str(tc) for tc in time_constants])  

    def on_list_sensitivities_change(self,sensitivities):
        """
        Fill the sensitivity combo box.

        Parameters
        ----------
        sensitivities : list of float
            Available sensitivities (V).
        """
        self.combo_Sensitivities.clear() #First we empty the combobox
        if len(sensitivities)>0:
                self.combo_Sensitivities.addItems([str(s) for s in sensitivities])

    def on_time_constant_change(self,t):
        """
        Select the current time constant in the combo box.

        Parameters
        ----------
        t : list
            ``[index, value]`` of the current time constant.
        """
        self.combo_TimeConstants.setCurrentIndex(t[0])

    def on_sensitivity_change(self,s):
        """
        Select the current sensitivity in the combo box.

        Parameters
        ----------
        s : list
            ``[index, value]`` of the current sensitivity.
        """
        self.combo_Sensitivities.setCurrentIndex(s[0])
         
    def on_refreshtime_change(self,value):
        """
        Show the refresh time.

        Parameters
        ----------
        value : float
            Refresh time (s).
        """
        self.edit_RefreshTime.setText(f"{value:.3f}")

    def on_sensitivity_auto_change(self,value):
        """
        Update the "Auto Sensitivity (Software)" checkbox, without triggering its event handler.

        Parameters
        ----------
        value : bool
            Status of the software auto-sensitivity.
        """
        self.box_SensitivityAuto.blockSignals(True)
        self.box_SensitivityAuto.setChecked(value)
        self.box_SensitivityAuto.blockSignals(False)

    def on_close(self):
        """
        Called when the interface is closed. Nothing to do for this GUI.
        """
        pass

#######################
### END Event Slots ###
#######################

###################################################################################################################################################
### GUI Events Functions. They are triggered by direct interaction with the GUI, and they call methods of the interface (i.e. the model) object.###
###################################################################################################################################################

    def click_button_refresh_list_devices(self):
        """
        Ask the interface to scan again for available devices.
        """
        self.interface.refresh_list_devices()

    def click_button_connect_disconnect(self):
        """
        Connect to the device selected in the combo box, or disconnect the connected device.
        """
        if(self.interface.instrument.connected == False): # We attempt connection   
            device_full_name = self.combo_Devices.currentText() # Get the device name from the combobox
            self.interface.connect_device(device_full_name)
        elif(self.interface.instrument.connected == True): # We attempt disconnection
            self.interface.disconnect_device()

    def click_box_data_to_change(self,data,state):
        """
        Select whether an output is read continuously, based on the state of its checkbox.

        Parameters
        ----------
        data : str
            Output name.
        state : int
            State of the checkbox (``QtCore.Qt.Checked`` or ``QtCore.Qt.Unchecked``).
        """
        if state == QtCore.Qt.Checked:
            self.interface.set_data_to_read(data,True)
        else:
            self.interface.set_data_to_read(data,False)
        return
            
    def click_button_set_auto_scale(self):
        """
        Run the auto-gain / auto-scale function of the instrument.
        """
        self.interface.set_auto_scale()

    def click_combo_time_constants(self):
        """
        Set the time constant selected in the combo box.
        """
        self.interface.set_time_constant(self.combo_TimeConstants.currentIndex())

    def click_combo_sensitivities(self):
        """
        Set the sensitivity selected in the combo box.
        """
        self.interface.set_sensitivity(self.combo_Sensitivities.currentIndex())

    def click_box_SensitivityAuto(self,state):
        """
        Turn the software auto-sensitivity on/off, based on the state of its checkbox.

        Parameters
        ----------
        state : int
            State of the checkbox (``QtCore.Qt.Checked`` or ``QtCore.Qt.Unchecked``).
        """
        if state == QtCore.Qt.Checked:
            status_bool = True
        else:
            status_bool = False
        self.interface.set_sensitivity_auto(status_bool)
        return
       
    def click_button_StartPauseReading(self): 
        """
        Start the continuous reading if it is paused, or pause it if it is running.
        """
        if(self.interface.continuous_read == False):
            self.interface.start_reading()
        elif (self.interface.continuous_read == True):
            self.interface.pause_reading()
        return

    def click_button_StopReading(self):
        """
        Stop the continuous reading and delete all accumulated data.
        """
        self.interface.stop_reading()

    def press_enter_refresh_time(self):
        """
        Set the refresh time typed in the refresh-time box.

        Returns
        -------
        bool
            ``True`` if the value was valid.
        """
        return self.interface.set_refresh_time(self.edit_RefreshTime.text())

    def press_enter_frequency(self):
        """
        Set the frequency typed in the frequency box. Ignored if the box is read-only (device does not allow
        setting the frequency).

        Returns
        -------
        bool or None
            Result of :meth:`interface.set_frequency`, or ``None`` if the box is read-only.
        """
        if self.edit_Frequency.isReadOnly():
            return
        self.edit_Frequency.setModified(False) #allows the edit to be updated with the value read back from the device
        return self.interface.set_frequency(self.edit_Frequency.text())

    def click_button_phase_step(self, delta):
        """
        Change the phase by a fixed step.

        Parameters
        ----------
        delta : int
            Phase change (deg): -10, -1, +1 or +10.

        Returns
        -------
        bool
            Result of :meth:`interface.step_phase`.
        """
        self.edit_Phase.setModified(False)
        return self.interface.step_phase(delta)

    def press_enter_phase(self):
        """
        Set the phase typed in the phase box. Ignored if the box is read-only.

        Returns
        -------
        bool or None
            Result of :meth:`interface.set_phase`, or ``None`` if the box is read-only.
        """
        if self.edit_Phase.isReadOnly():
            return
        self.edit_Phase.setModified(False)
        return self.interface.set_phase(self.edit_Phase.text())

############################################################
### END GUI Events Functions
############################################################

 
class MainWindow(Qt.QWidget):
    """
    Main window used when the GUI is run as a stand-alone application (see :func:`main`).
    """
    def __init__(self):
        """
        Create the window and set its title to the package name.
        """
        super().__init__()
        self.setWindowTitle(__package__)
        # Set the central widget of the Window.
        # self.setCentralWidget(self.container)
    def closeEvent(self, event):
        """
        Handle the window close event. Nothing to do: the interface is closed via ``app.aboutToQuit``.

        Parameters
        ----------
        event : QtGui.QCloseEvent
            The close event.
        """
        pass

def main():
    """
    Start the GUI as a stand-alone application (entry point ``pySRSLockin``).

    Command-line arguments
    ----------------------
    -s, --decrease_verbose
        Decrease the verbosity of the logs.
    """
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
