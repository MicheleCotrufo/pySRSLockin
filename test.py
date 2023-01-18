import pyvisa as visa
rm = visa.ResourceManager()
print(rm.list_resources())
addr="GPIB0::8::INSTR"
addr='USB0::0xB506::0x2000::004418::INSTR'
instrument = rm.open_resource(addr)
print(instrument.query('*IDN?').strip())
instrument.query('OUTP? 0')
instrument.write('ASCL')
instrument.close()


from driver import SRS_Lockin
lockin = SRS_Lockin()
lockin.list_devices()

lockin.connect_device('USB0::0xB506::0x2000::004418::INSTR')

print(lockin.X)
print(lockin.Y)
print(lockin.magnitude)
print(lockin.theta)
print(lockin.frequency)
print(lockin.phase)

print(lockin.set_auto_scale())

print(lockin.time_constant)

lockin.time_constant = 0