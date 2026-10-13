"""
Low-level driver for Stanford Research Systems (SRS) lock-in amplifiers.

Supported models: SR865A, SR844, SR810, SR510.

All models are accessed through the same class, :class:`SRS_Lockin`. Model-specific commands, ranges and
capabilities are stored in class-level tables (:attr:`SRS_Lockin.mapping_properties`,
:attr:`SRS_Lockin._sensitivities`, :attr:`SRS_Lockin._time_constants`), so that the public API is the same
for every model. Features that a model does not support (e.g. Y, R and theta on the SR510) raise a
``RuntimeError`` when accessed; :meth:`SRS_Lockin.supports_property` and :attr:`SRS_Lockin.supported_outputs`
can be used to check in advance.

Indexing convention for time_constant / sensitivity
---------------------------------------------------
:attr:`SRS_Lockin.time_constants` and :attr:`SRS_Lockin.sensitivities` are lists of values (in s and V).
The integer used by the :attr:`SRS_Lockin.time_constant` and :attr:`SRS_Lockin.sensitivity` properties is
the POSITION in these lists. For SR865A, SR844 and SR810 the position coincides with the integer code used by
the instrument. For the SR510 the instrument codes start from 1 (and sensitivity codes 1-3 are missing when no
preamplifier is installed); the driver converts positions <-> instrument codes internally.

Note: most of docstrings in this file have been generated automatically by Claude. AI can make mistakes.
"""

import math
import operator
import pyvisa as visa


class SRS_Lockin:
    """
    Low-level driver to communicate with SRS lock-in amplifiers (SR865A, SR844, SR810, SR510) via VISA.

    The models SR865A, SR844 and SR810 are identified via their answer to ``*IDN?``. The SR510 does not
    support ``*IDN?``: any device that times out on ``*IDN?`` is probed with a few read-only SR510 commands
    (see :meth:`check_if_valid_old_SRS_instrument`).

    Attributes
    ----------
    model_identifiers : list of [str, str]
        Class attribute. Each element is ``[model_name, idn_substring]``. A device is recognized as
        ``model_name`` if ``idn_substring`` is contained in its answer to ``*IDN?``. For the SR510 (which
        does not answer ``*IDN?``) the string is only used as its identity.
    new_models : list of str
        Class attribute. Models that support ``*IDN?`` and IEEE-488.2 common commands.
    old_models : list of str
        Class attribute. Models that do not support ``*IDN?`` and are identified by probing.
    mapping_properties : dict
        Class attribute. ``{property_name: {model: command_template}}``. ``'{}'`` in a template is replaced
        by the value to set. If a model is missing from the inner dictionary, the property is not
        supported by that model.
    output_names : list of str
        Class attribute. Names of all outputs that a lock-in may provide:
        ``['X', 'Y', 'mag', 'theta', 'aux1', 'aux2']``.
    rm : pyvisa.ResourceManager
        The PyVISA resource manager used to discover and open VISA resources.
    instrument : pyvisa.resources.MessageBasedResource
        The VISA resource of the connected device. Only defined after a successful connection.
    connected : bool
        ``True`` if a device is currently connected, ``False`` otherwise.
    model : str or None
        Model of the device currently connected (e.g. ``'SR510'``), or ``None`` if not connected.
    model_user : str or None
        Model specified by the user when creating this driver (if any). When set, only devices of this
        model are returned by :meth:`list_devices`.
    only_new_models : bool
        If ``True``, :meth:`list_devices` does not look for old models (SR510).
    scan_serial_ports : bool
        If ``True``, :meth:`list_devices` also scans serial (``ASRL``) resources.
    timeout_ms : int
        VISA timeout (in ms) used for all communications.
    list_supported_models : list of str
        Names of all supported models.
    list_valid_devices : list of [str, str, str]
        Result of the last call to :meth:`list_devices`.
    """

    # ------------------------------------------------------------------------------------------------
    # Model specifications
    # ------------------------------------------------------------------------------------------------
    # model_identifiers: [model name, string contained in the answer to '*IDN?'].
    # The SR510 does not support '*IDN?'; its entry is kept for uniformity, and the string is used as its "identity".
    model_identifiers = [
        ['SR865A', 'Stanford_Research_Systems,SR865A'],
        ['SR844',  'Stanford_Research_Systems,SR844'],
        ['SR810',  'Stanford_Research_Systems,SR810'],
        ['SR510',  'Stanford_Research_Systems,SR510'],
    ]

    new_models = ['SR865A', 'SR844', 'SR810']  # support '*IDN?' and IEEE-488.2 common commands
    old_models = ['SR510']                     # do not support '*IDN?'; identified by probing

    # Sensitivities and time constants. Each entry is a list of (instrument_code, value) pairs,
    # listed in order of increasing instrument code.
    _sensitivities = {
        # SR865A: SCAL 0 = 1 V ... SCAL 27 = 1 nV (manual p. 112)
        'SR865A': list(enumerate([1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9,
                                  500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6,
                                  200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
                                  50e-3, 100e-3, 200e-3, 500e-3, 1][::-1])),
        # SR844: SENS 0 = 100 nV ... SENS 14 = 1 V
        'SR844':  list(enumerate([100e-9, 300e-9, 1e-6, 3e-6, 10e-6, 30e-6, 100e-6,
                                  300e-6, 1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1])),
        # SR810: SENS 0 = 2 nV ... SENS 26 = 1 V (manual p. 5-6)
        'SR810':  list(enumerate([2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9,
                                  500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6,
                                  200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3,
                                  50e-3, 100e-3, 200e-3, 500e-3, 1])),
        # SR510: G1 = 10 nV ... G24 = 500 mV (manual p. 17). G1-G3 only with preamp.
        'SR510':  list(enumerate([10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9, 1e-6, 2e-6, 5e-6,
                                  10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6, 1e-3, 2e-3, 5e-3,
                                  10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3], start=1)),
    }
    _time_constants = {
        # SR865A: OFLT 0 = 1 us ... OFLT 21 = 30 ks (manual p. 113)
        'SR865A': list(enumerate([1e-6, 3e-6, 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3,
                                  30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3,
                                  3e3, 10e3, 30e3])),
        # SR844: OFLT 0 = 100 us ... OFLT 17 = 30 ks
        'SR844':  list(enumerate([100e-6, 300e-6, 1e-3, 3e-3, 10e-3,
                                  30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3,
                                  3e3, 10e3, 30e3])),
        # SR810: OFLT 0 = 10 us ... OFLT 19 = 30 ks (manual p. 5-6)
        'SR810':  list(enumerate([10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3,
                                  30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3,
                                  3e3, 10e3, 30e3])),
        # SR510 (pre-filter): T1,1 = 1 ms ... T1,11 = 100 s (manual p. 19)
        'SR510':  list(enumerate([1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100], start=1)),
    }

    # Command templates. '{}' is replaced by the value to set. A missing model key means "not supported".
    # SR510 notes: commands are single letters, spaces are ignored, ';' separates commands (manual p. 15).
    #   All SR510 commands start with a space: in practice, the SR510 was not detected without it (tested on real hardware).
    #   ' S0;Q' first sets the output display to X, then reads it (the SR510 only measures X).
    mapping_properties = {
        'X':                {'SR865A': 'OUTP? 0', 'SR844': 'OUTP? 1', 'SR810': 'OUTP? 1', 'SR510': ' S0;Q'},
        'Y':                {'SR865A': 'OUTP? 1', 'SR844': 'OUTP? 2', 'SR810': 'OUTP? 2'},
        'mag':              {'SR865A': 'OUTP? 2', 'SR844': 'OUTP? 3', 'SR810': 'OUTP? 3'},
        'theta':            {'SR865A': 'OUTP? 3', 'SR844': 'OUTP? 5', 'SR810': 'OUTP? 4'},
        'aux1':             {'SR865A': 'OAUX? 0', 'SR844': 'AUXI? 1', 'SR810': 'OAUX? 1', 'SR510': ' X1'},
        'aux2':             {'SR865A': 'OAUX? 1', 'SR844': 'AUXI? 2', 'SR810': 'OAUX? 2', 'SR510': ' X2'},
        'time_constant_READ': {'SR865A': 'OFLT?',   'SR844': 'OFLT?',   'SR810': 'OFLT?',   'SR510': ' T1'},
        'time_constant_SET':  {'SR865A': 'OFLT {}', 'SR844': 'OFLT {}', 'SR810': 'OFLT {}', 'SR510': ' T1,{}'},
        'sensitivity_READ':   {'SR865A': 'SCAL?',   'SR844': 'SENS?',   'SR810': 'SENS?',   'SR510': ' G'},
        'sensitivity_SET':    {'SR865A': 'SCAL {}', 'SR844': 'SENS {}', 'SR810': 'SENS {}', 'SR510': ' G{}'},
        'frequency_READ':     {'SR865A': 'FREQ?',   'SR844': 'FREQ?',   'SR810': 'FREQ?',   'SR510': ' F'},
        'frequency_SET':      {'SR865A': 'FREQ {}', 'SR844': 'FREQ {}', 'SR810': 'FREQ {}'},  # SR510: F is read-only. Others: internal reference only
        'phase_READ':         {'SR865A': 'PHAS?',   'SR844': 'PHAS?',   'SR810': 'PHAS?',   'SR510': ' P'},
        'phase_SET':          {'SR865A': 'PHAS {}', 'SR844': 'PHAS {}', 'SR810': 'PHAS {}', 'SR510': ' P{}'},
        'auto_sensitivity':   {'SR865A': 'ASCL',    'SR844': 'AGAN',    'SR810': 'AGAN'},     # SR510 has no auto-gain command
        'status_byte':        {'SR865A': '*STB?',   'SR844': '*STB?',   'SR810': '*STB?',   'SR510': ' Y'},
    }

    # Codes used by SNAP? to read several outputs at the same instant. Only models whose manual was checked are listed.
    # SR865A: SNAP? accepts 2-3 parameters, codes as OUTP? (manual p. 132). SR810: 2-6 parameters (manual p. 5-15).
    _snap_codes = {
        'SR865A': {'X': 0, 'Y': 1, 'mag': 2, 'theta': 3, 'aux1': 4, 'aux2': 5},
        'SR810':  {'X': 1, 'Y': 2, 'mag': 3, 'theta': 4, 'aux1': 5, 'aux2': 6},
    }
    _snap_max_params = {'SR865A': 3, 'SR810': 6}

    output_names = ['X', 'Y', 'mag', 'theta', 'aux1', 'aux2']

    # VISA settings for the SR510 (manual p. 7, 15, 22). Responses end with <cr> on RS232 (echo off) and <cr><lf> on GPIB.
    # NOTE: never call instrument.clear() on an SR510: a GPIB Device Clear resets the instrument (same as 'Z').
    _SR510_serial_settings = {'baud_rate': 9600, 'data_bits': 8, 'stop_bits': visa.constants.StopBits.two,
                              'parity': visa.constants.Parity.none}

    def __init__(self, model=None, only_new_models=False, scan_serial_ports=False, timeout_ms=2000):
        """
        Parameters
        ----------
        model : str, optional
            If specified, the driver will only look for devices of this model. Must be one of the models
            listed in :attr:`model_identifiers` (``'SR865A'``, ``'SR844'``, ``'SR810'``, ``'SR510'``).
        only_new_models : bool, optional
            Older models (SR510) do not answer ``*IDN?`` and are identified indirectly, by sending a few
            read-only SR510 commands to any device that times out on ``*IDN?``. This slows down
            :meth:`list_devices`. If ``True``, older models are ignored. Default is ``False``.
        scan_serial_ports : bool, optional
            If ``False`` (default), serial ports (``ASRL`` resources) are skipped by :meth:`list_devices`.
            A device on a serial port can always be connected directly with
            ``connect_device(addr, model=...)``.
        timeout_ms : int, optional
            VISA timeout (in ms) used for all communications. Default is 2000.

        Raises
        ------
        RuntimeError
            If ``model`` is specified but is not one of the supported models.
        """
        self.list_supported_models = [m[0] for m in self.model_identifiers]
        if model and model not in self.list_supported_models:
            raise RuntimeError("The specified model is not supported. Supported models are " + ", ".join(self.list_supported_models))
        self.model_user = model
        self.only_new_models = only_new_models
        self.scan_serial_ports = scan_serial_ports
        self.timeout_ms = timeout_ms
        self.rm = visa.ResourceManager()
        self.model = None
        self.connected = False
        self.list_valid_devices = []
        self._reset_state()

    def _reset_state(self):
        """
        Reset the cached state that depends on the connected device (current time constant and sensitivity,
        and the tables of available time constants and sensitivities). Called at creation and after
        disconnection.
        """
        self._time_constant = None
        self._sensitivity = None
        self._tc_table = None    # list of (instrument_code, value) for the connected device
        self._sens_table = None

    # ------------------------------------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------------------------------------
    @staticmethod
    def _is_timeout(error):
        """
        Check whether an exception is a VISA timeout.

        Parameters
        ----------
        error : Exception
            The exception to check.

        Returns
        -------
        bool
            ``True`` if ``error`` is a ``pyvisa.VisaIOError`` with error code ``VI_ERROR_TMO``.
        """
        return isinstance(error, visa.VisaIOError) and error.error_code == visa.constants.StatusCode.error_timeout

    def _configure_resource(self, instrument, model):
        """
        Configure an open VISA resource (timeout, terminations and, for serial ports, serial settings)
        for the given model.

        For SR865A, SR844 and SR810 only the timeout is set, and the pyvisa defaults are kept for everything
        else. For the SR510, commands are terminated by ``\\r``; answers end with ``\\r`` on RS232 and with
        ``\\r\\n`` on GPIB. On serial ports, the SR510 is set to 9600 baud, 8 data bits, 2 stop bits,
        no parity (the factory setting of its rear-panel switches).

        Parameters
        ----------
        instrument : pyvisa.resources.MessageBasedResource
            The open VISA resource.
        model : str
            Model of the device behind the resource.
        """
        instrument.timeout = self.timeout_ms
        if model == 'SR510':
            instrument.write_termination = '\r'
            if instrument.resource_name.startswith('ASRL'):
                instrument.read_termination = '\r'
                for k, v in self._SR510_serial_settings.items():
                    setattr(instrument, k, v)
            else:
                instrument.read_termination = '\r\n'

    def _cmd(self, prop):
        """
        Return the command template of a property for the connected model.

        Parameters
        ----------
        prop : str
            A key of :attr:`mapping_properties` (e.g. ``'X'``, ``'sensitivity_SET'``).

        Returns
        -------
        str
            The command template. Templates of "SET" properties contain ``'{}'``, to be replaced with the value.

        Raises
        ------
        RuntimeError
            If no device is connected, or if the connected model does not support ``prop``.
        """
        self.check_valid_connection()
        cmd = self.mapping_properties[prop].get(self.model)
        if cmd is None:
            raise RuntimeError(f"Property '{prop}' is not available for model {self.model}.")
        return cmd

    def _query(self, prop):
        """
        Send the query associated to a property and return the answer.

        Parameters
        ----------
        prop : str
            A key of :attr:`mapping_properties`.

        Returns
        -------
        str
            Answer of the instrument, with leading/trailing whitespace removed.

        Raises
        ------
        RuntimeError
            If no device is connected, or if the connected model does not support ``prop``.
        pyvisa.VisaIOError
            If the communication fails (e.g. timeout).
        """
        return self.instrument.query(self._cmd(prop)).strip()

    def _write(self, prop, value):
        """
        Send the command associated to a property, with ``'{}'`` in its template replaced by ``value``.

        Parameters
        ----------
        prop : str
            A key of :attr:`mapping_properties` (typically a ``'..._SET'`` key).
        value
            Value inserted in the command template.

        Raises
        ------
        RuntimeError
            If no device is connected, or if the connected model does not support ``prop``.
        pyvisa.VisaIOError
            If the communication fails.
        """
        self.instrument.write(self._cmd(prop).format(value))

    # ------------------------------------------------------------------------------------------------
    # Identification of old models
    # ------------------------------------------------------------------------------------------------
    def check_if_valid_old_SRS_instrument(self, instrument):
        """
        Check whether an open VISA resource is an SR510.

        The SR510 does not support ``*IDN?``. It is identified by sending three read-only commands and
        checking that the answers are in the expected ranges: ``G`` (sensitivity code, 1-24), ``H``
        (preamplifier status, 0 or 1) and ``T1`` (pre-filter time constant code, 1-11). If the check is
        successful, the status byte is read (``Y``), which clears the "unrecognized command" error caused
        by a previous ``*IDN?``.

        The VISA resource is (re)configured for the SR510 (terminations, serial settings) before probing.

        Parameters
        ----------
        instrument : pyvisa.resources.MessageBasedResource
            The open VISA resource to check.

        Returns
        -------
        list of [str, str] or None
            ``['SR510', 'Stanford_Research_Systems,SR510']`` if the device is an SR510, ``None`` otherwise.
            Communication errors are not raised: they result in ``None``.
        """
        self._configure_resource(instrument, 'SR510')
        try:
            instrument.write('')  # sends a lone <cr>: flushes any garbage left on the SR510 command line (manual p. 21)
            g = int(instrument.query(' G').strip())
            h = int(instrument.query(' H').strip())
            t = int(instrument.query(' T1').strip())
            if 1 <= g <= 24 and h in (0, 1) and 1 <= t <= 11:
                instrument.query(' Y')  # reading the status byte clears the 'unrecognized command' bit set by '*IDN?'
                return ['SR510', 'Stanford_Research_Systems,SR510']
        except Exception:
            pass
        return None

    def _identify(self, instrument):
        """
        Identify the device behind an open VISA resource.

        The device is first queried with ``*IDN?`` (unless the user restricted the driver to old models).
        If the query times out, and old models are not excluded, the device is probed with
        :meth:`check_if_valid_old_SRS_instrument`. Devices of a model different from :attr:`model_user`
        (if set) are discarded.

        Parameters
        ----------
        instrument : pyvisa.resources.MessageBasedResource
            The open VISA resource.

        Returns
        -------
        list of [str, str] or None
            ``[identity, model]`` if the device is a supported lock-in, ``None`` otherwise.
        """
        try_new = self.model_user in (None, *self.new_models)
        try_old = (not self.only_new_models) and self.model_user in (None, *self.old_models)
        if try_new:
            try:
                idn = instrument.query('*IDN?').strip()
                for model, identifier in self.model_identifiers:
                    if identifier in idn and model in self.new_models:
                        if self.model_user and self.model_user != model:
                            return None
                        return [idn, model]
                return None  # device answered *IDN?, but it is not a supported model
            except visa.VisaIOError as e:
                if not self._is_timeout(e):
                    return None
        if try_old:
            result = self.check_if_valid_old_SRS_instrument(instrument)
            if result:
                return [result[1], result[0]]
        return None

    # ------------------------------------------------------------------------------------------------
    # Device scan / connection
    # ------------------------------------------------------------------------------------------------
    def list_devices(self):
        """
        Scan all VISA resources visible to the system and check whether any of them is a supported SRS
        lock-in (see :meth:`_identify`).

        Serial (``ASRL``) resources are skipped unless :attr:`scan_serial_ports` is ``True``. The device
        currently connected (if any) is listed without being re-opened. If :attr:`model_user` was set, only
        devices of that model are returned.

        Returns
        -------
        list_valid_devices : list of [str, str, str]
            A list of all valid devices found. Each element is a list of three strings, in the format
            ``[address, identity, model]``, where ``address`` is the VISA resource address, ``identity`` is
            the answer to ``*IDN?`` (or ``'Stanford_Research_Systems,SR510'`` for the SR510), and ``model``
            is the model name. The list is also stored in :attr:`list_valid_devices`.
        """
        self.list_all_devices = self.rm.list_resources()
        self.list_valid_devices = []
        for addr in self.list_all_devices:
            if addr.startswith('ASRL') and not self.scan_serial_ports:
                continue
            if self.connected and addr == getattr(self.instrument, 'resource_name', None):
                self.list_valid_devices.append([addr, self._identity, self.model])  # do not re-open the connected device
                continue
            instrument = None
            try:
                instrument = self.rm.open_resource(addr)
                instrument.timeout = self.timeout_ms
                result = self._identify(instrument)
                if result:
                    self.list_valid_devices.append([addr, result[0], result[1]])
            except Exception:
                pass
            finally:
                if instrument is not None:
                    try:
                        instrument.close()
                    except Exception:
                        pass
        return self.list_valid_devices

    def connect_device(self, device_addr, model=None):
        """
        Connect to the device at ``device_addr``.

        If ``model`` is not specified, the model is taken from the last device scan (a new scan is run if
        ``device_addr`` is not in :attr:`list_valid_devices`). If ``model`` is specified, no scan is run.
        In both cases the identity of the device is verified before connecting (``*IDN?`` for the new
        models, :meth:`check_if_valid_old_SRS_instrument` for the SR510). After connection,
        :meth:`additional_checks` is called.

        Parameters
        ----------
        device_addr : str
            VISA resource address of the device (e.g. ``'GPIB0::8::INSTR'``).
        model : str, optional
            Model of the device. Needed to connect to a device on a serial port, when serial ports are
            not scanned.

        Returns
        -------
        (Msg, ID) : (str, int)
            ``Msg`` is the identity of the connected device, or an error message. ``ID`` is 1 if the
            connection was successful, 0 otherwise.

        Raises
        ------
        RuntimeError
            If a device is already connected.
        ValueError
            If ``model`` is not a supported model, or if ``model`` is not specified and ``device_addr`` does
            not correspond to any supported device found by :meth:`list_devices`.
        """
        if self.connected:
            raise RuntimeError("A device is already connected. Disconnect it first.")
        if model is not None and model not in self.list_supported_models:
            raise ValueError("The specified model is not supported. Supported models are " + ", ".join(self.list_supported_models))

        if model is None:
            known = {dev[0]: dev for dev in self.list_valid_devices}
            if device_addr not in known:
                self.list_devices()
                known = {dev[0]: dev for dev in self.list_valid_devices}
            if device_addr not in known:
                raise ValueError("The specified address is not a valid device address.")
            model = known[device_addr][2]

        try:
            instrument = self.rm.open_resource(device_addr)
            self._configure_resource(instrument, model)
            if model in self.new_models:
                idn = instrument.query('*IDN?').strip()
                identifier = dict(self.model_identifiers)[model]
                if identifier not in idn:
                    instrument.close()
                    return (f"Device at {device_addr} identifies as '{idn}', not as {model}.", 0)
                Msg = idn
            else:  # SR510
                if not self.check_if_valid_old_SRS_instrument(instrument):
                    instrument.close()
                    return (f"Device at {device_addr} does not respond as an {model}.", 0)
                Msg = dict(self.model_identifiers)[model]
        except visa.VisaIOError as e:
            return ("Error while connecting: " + str(e), 0)

        self.instrument = instrument
        self.model = model
        self._identity = Msg
        self.connected = True
        self._tc_table = list(self._time_constants[model])     # copies: never modify the class-level tables
        self._sens_table = list(self._sensitivities[model])
        try:
            self.additional_checks()
        except Exception as e:
            self.disconnect_device()
            return ("Error while configuring the device: " + str(e), 0)
        return (Msg, 1)

    def additional_checks(self):
        """
        Perform model-specific adjustments right after connection. Called automatically by
        :meth:`connect_device`.

        For the SR510: the instrument is set to remote mode (``I1``; GPIB REN is not implemented on the
        SR510), and the presence of the preamplifier is checked (``H``). Without preamplifier, the
        sensitivities below 100 nV are removed from :attr:`sensitivities`.
        """
        if self.model == 'SR510':
            self.instrument.write(' I1')  # remote mode (GPIB REN is not implemented on the SR510, manual p. 18)
            # Sensitivities below 100 nV (codes 1-3) require the preamplifier (manual p. 17)
            if int(self.instrument.query(' H').strip()) == 0:
                self._sens_table = [(c, v) for (c, v) in self._sens_table if c >= 4]

    def disconnect_device(self):
        """
        Disconnect the currently connected device.

        The device is set back to local mode before closing the connection (``I0`` for the SR510; REN line
        deasserted for the other models, when supported by the interface).

        Returns
        -------
        (Msg, ID) : (str or Exception, int)
            ``Msg`` is a confirmation message, or the exception raised during disconnection. ``ID`` is 1 if
            the disconnection was successful, 0 otherwise.

        Raises
        ------
        RuntimeError
            If no device is connected.
        """
        if not self.connected:
            raise RuntimeError("Device is already disconnected.")
        try:
            if self.model == 'SR510':
                self.instrument.write(' I0')  # back to local
            else:
                try:
                    self.instrument.control_ren(visa.constants.RENLineOperation.deassert)  # disable remote mode
                except (visa.VisaIOError, AttributeError, NotImplementedError):
                    pass  # e.g. serial resources do not support REN
            self.instrument.close()
            Msg, ID = 'Succesfully disconnected.', 1
        except Exception as e:
            Msg, ID = e, 0
        if ID == 1:
            self.connected = False
            self.model = None
            self._reset_state()
        return (Msg, ID)

    def check_valid_connection(self):
        """
        Verify that a device is currently connected.

        Raises
        ------
        RuntimeError
            If no device is currently connected.
        """
        if not self.connected:
            raise RuntimeError("No device is currently connected.")

    def supports_property(self, prop):
        """
        Check whether the connected model supports a property.

        Parameters
        ----------
        prop : str
            A key of :attr:`mapping_properties` (e.g. ``'Y'``, ``'frequency_SET'``, ``'auto_sensitivity'``).
            Unknown keys return ``False``.

        Returns
        -------
        bool
            ``True`` if the connected model supports ``prop``.

        Raises
        ------
        RuntimeError
            If no device is connected.
        """
        self.check_valid_connection()
        return self.model in self.mapping_properties.get(prop, {})

    # ------------------------------------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------------------------------------
    def output_property(name):
        """
        Create a read-only property that queries the output ``name`` (a key of :attr:`mapping_properties`)
        and returns it as a float. Used at class creation to define :attr:`X`, :attr:`Y`, :attr:`mag`,
        :attr:`theta`, :attr:`aux1`, :attr:`aux2`, and then deleted from the class namespace.
        """
        @property
        def prop(self):
            return float(self._query(name))
        prop.__doc__ = (f"float: Current value of the output '{name}', read from the instrument. "
                        f"Raises RuntimeError if no device is connected or if the connected model does not provide '{name}'.")
        return prop

    X, Y, mag, theta = output_property('X'), output_property('Y'), output_property('mag'), output_property('theta')
    aux1, aux2 = output_property('aux1'), output_property('aux2')
    del output_property

    @property
    def supported_outputs(self):
        """
        list of str: Outputs (among :attr:`output_names`) provided by the connected model.
        For example, ``['X', 'aux1', 'aux2']`` for the SR510. Raises ``RuntimeError`` if no device is connected.
        """
        return [n for n in self.output_names if self.supports_property(n)]

    def read_outputs(self, names):
        """
        Read several outputs.

        When the model supports it (SR865A, SR810), the values are acquired at the same instant with
        ``SNAP?`` (in groups of at most the number of parameters accepted by the model: 3 for the SR865A,
        6 for the SR810). Otherwise, outputs are read one by one.

        Parameters
        ----------
        names : iterable of str
            Names of the outputs to read (elements of :attr:`output_names`).

        Returns
        -------
        dict
            ``{name: value}`` for each requested output. Values are floats (V for X, Y, mag, aux1, aux2;
            degrees for theta).

        Raises
        ------
        RuntimeError
            If no device is connected, or if any of the requested outputs is not provided by the connected model.
        """
        self.check_valid_connection()
        names = list(names)
        unsupported = [n for n in names if not self.supports_property(n)]
        if unsupported:
            raise RuntimeError(f"{', '.join(unsupported)} not available for model {self.model}.")
        result = {}
        codes = self._snap_codes.get(self.model)
        if codes and len(names) >= 2:
            nmax = self._snap_max_params[self.model]
            groups = [names[i:i + nmax] for i in range(0, len(names), nmax)]
            if len(groups[-1]) == 1:            # SNAP? needs at least 2 parameters
                groups[-1] = groups[-2][-1:] + groups[-1]
                groups[-2] = groups[-2][:-1]
            for g in groups:
                answer = self.instrument.query('SNAP? ' + ','.join(str(codes[n]) for n in g))
                for n, v in zip(g, answer.strip().split(',')):
                    result[n] = float(v)
        else:
            for n in names:
                result[n] = getattr(self, n)
        return result

    @property
    def status_byte(self):
        """
        int: Raw status byte of the instrument (``*STB?``; ``Y`` for the SR510). The meaning of each bit is
        model-dependent (see the manual of each model). On the SR510, reading the status byte also clears it.
        """
        return int(self._query('status_byte'))

    # ------------------------------------------------------------------------------------------------
    # Reference
    # ------------------------------------------------------------------------------------------------
    @property
    def frequency(self):
        """
        float: Reference frequency (Hz).

        Setting it is only effective when the internal reference is used, and it is not possible on the
        SR510 (``RuntimeError``). Read it back after setting it, to check the value actually applied.
        """
        return float(self._query('frequency_READ'))

    @frequency.setter
    def frequency(self, f):
        self._write('frequency_SET', float(f))

    @property
    def phase(self):
        """
        float: Reference phase shift (degrees).

        When setting it, the instrument may wrap the value into its own range (e.g. -180 to 180 deg for the
        SR865A). Read it back after setting it, to check the value actually applied.
        """
        return float(self._query('phase_READ'))

    @phase.setter
    def phase(self, p):
        self._write('phase_SET', float(p))

    # ------------------------------------------------------------------------------------------------
    # Time constant and sensitivity
    # ------------------------------------------------------------------------------------------------
    @property
    def time_constants(self):
        """
        list of float: Time constants (s) available on the connected device. The position in the list is the
        index used by :attr:`time_constant`. Raises ``RuntimeError`` if no device is connected.
        """
        self.check_valid_connection()
        return [v for (_, v) in self._tc_table]

    @property
    def sensitivities(self):
        """
        list of float: Full-scale sensitivities (V) available on the connected device. The position in the list
        is the index used by :attr:`sensitivity`. The order follows the instrument codes, so it is decreasing
        for the SR865A and increasing for the other models. Raises ``RuntimeError`` if no device is connected.
        """
        self.check_valid_connection()
        return [v for (_, v) in self._sens_table]

    def _read_index(self, prop, table):
        """
        Read an instrument code (time constant or sensitivity) and convert it to a position in ``table``.

        Parameters
        ----------
        prop : str
            ``'time_constant_READ'`` or ``'sensitivity_READ'``.
        table : list of (int, float)
            ``(instrument_code, value)`` pairs available on the connected device.

        Returns
        -------
        int or None
            Position of the current setting in ``table``, or ``None`` if it could not be read or is not in
            ``table``.

        Raises
        ------
        RuntimeError
            If no device is connected.
        """
        try:
            code = int(self._query(prop))
        except (RuntimeError, ValueError, visa.VisaIOError):
            if not self.connected:
                raise
            return None
        codes = [c for (c, _) in table]
        return codes.index(code) if code in codes else None

    def _set_index(self, prop, table, index, label):
        """
        Set a time constant or sensitivity, given its position in ``table``.

        Parameters
        ----------
        prop : str
            ``'time_constant_SET'`` or ``'sensitivity_SET'``.
        table : list of (int, float)
            ``(instrument_code, value)`` pairs available on the connected device.
        index : int
            Position in ``table`` of the setting to apply.
        label : str
            Name used in the error message.

        Returns
        -------
        int
            ``index``.

        Raises
        ------
        RuntimeError
            If no device is connected.
        ValueError
            If ``index`` is not an integer between 0 and ``len(table) - 1`` (booleans are rejected).
        """
        self.check_valid_connection()
        try:
            index = -1 if isinstance(index, bool) else operator.index(index)
        except TypeError:
            index = -1
        if not (0 <= index < len(table)):
            raise ValueError(f"{label} must be an integer between 0 and {len(table) - 1}.")
        self._write(prop, table[index][0])
        return index

    @property
    def time_constant(self):
        """
        int or None: Index (position in :attr:`time_constants`) of the current time constant. ``None`` if it
        could not be read. Setting a value outside ``0 ... len(time_constants)-1`` raises ``ValueError``.
        """
        self.check_valid_connection()
        self._time_constant = self._read_index('time_constant_READ', self._tc_table)
        return self._time_constant

    @time_constant.setter
    def time_constant(self, index):
        self._time_constant = self._set_index('time_constant_SET', self._tc_table, index, 'time_constant')

    @property
    def sensitivity(self):
        """
        int or None: Index (position in :attr:`sensitivities`) of the current sensitivity. ``None`` if it could
        not be read. Setting a value outside ``0 ... len(sensitivities)-1`` raises ``ValueError``.
        """
        self.check_valid_connection()
        self._sensitivity = self._read_index('sensitivity_READ', self._sens_table)
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, index):
        self._sensitivity = self._set_index('sensitivity_SET', self._sens_table, index, 'sensitivity')

    @property
    def time_constant_value(self):
        """
        float or None: Current time constant (s). When set, the available time constant closest (on a
        logarithmic scale) to the given value is selected. Setting a value <= 0 raises ``ValueError``.
        """
        i = self.time_constant
        return None if i is None else self.time_constants[i]

    @time_constant_value.setter
    def time_constant_value(self, value):
        if not value > 0:
            raise ValueError("The time constant must be a positive number.")
        tcs = self.time_constants
        self.time_constant = min(range(len(tcs)), key=lambda i: abs(math.log(tcs[i] / value)))

    @property
    def sensitivity_value(self):
        """
        float or None: Current full-scale sensitivity (V). When set, the smallest available sensitivity
        larger than or equal to the given value is selected (the largest one, if the value exceeds all of them).
        """
        i = self.sensitivity
        return None if i is None else self.sensitivities[i]

    @sensitivity_value.setter
    def sensitivity_value(self, value):
        s = self.sensitivities
        candidates = [i for i in range(len(s)) if s[i] >= value]
        self.sensitivity = min(candidates, key=lambda i: s[i]) if candidates else max(range(len(s)), key=lambda i: s[i])

    def set_auto_scale(self):
        """
        Run the instrument auto-gain / auto-scale function (``ASCL`` on the SR865A, ``AGAN`` on the SR844
        and SR810). The SR510 does not have this function.

        Returns
        -------
        int
            1 if the command was sent, 0 if it failed or if the function is not supported by the connected model.

        Raises
        ------
        RuntimeError
            If no device is connected.
        """
        self.check_valid_connection()
        if self.model not in self.mapping_properties['auto_sensitivity']:
            return 0
        try:
            self.instrument.write(self.mapping_properties['auto_sensitivity'][self.model])
            return 1
        except visa.VisaIOError:
            return 0
