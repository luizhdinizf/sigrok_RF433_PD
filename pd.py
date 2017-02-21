##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Luiz Henrique <luizhdinizf@gmail.com>
## 
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd

class SamplerateError(Exception):
    pass

def normalize_time(t):
    if t >= 1.0:
        return '%.3f s  (%.3f Hz)' % (t, (1/t))
    elif t >= 0.001:
        if 1/t/1000 < 1:
            return '%.3f ms (%.3f Hz)' % (t * 1000.0, (1/t))
        else:
            return '%.3f ms (%.3f kHz)' % (t * 1000.0, (1/t)/1000)
    elif t >= 0.000001:
        if 1/t/1000/1000 < 1:
            return '%.3f μs (%.3f kHz)' % (t * 1000.0 * 1000.0, (1/t)/1000)
        else:
            return '%.3f μs (%.3f MHz)' % (t * 1000.0 * 1000.0, (1/t)/1000/1000)
    elif t >= 0.000000001:
        if 1/t/1000/1000/1000:
            return '%.3f ns (%.3f MHz)' % (t * 1000.0 * 1000.0 * 1000.0, (1/t)/1000/1000)
        else:
            return '%.3f ns (%.3f GHz)' % (t * 1000.0 * 1000.0 * 1000.0, (1/t)/1000/1000/1000)
    else:
        return '%f' % t

class Decoder(srd.Decoder):
    api_version = 3
    id = 'rf433'
    name = 'RF 433'
    longname = 'decoder for learning code'
    desc = 'view information on rf'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['data']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('time', 'Time'),
        ('3bit', '3bit'),
        ('field', 'Field'),
    )
    annotation_rows = (
        ('time', 'Time', (0,)),
        ('3bit', '3bit', (1,)),
        ('field', 'Field', (2,)),
    )
    options = (
        { 'id': 'add_size', 'desc': 'ADDRESS FIELD SIZE', 'default': 22 },
    )

    def __init__(self):
        self.samplerate = None
        self.oldpin = None
        self.last_samplenum = None
        self.buff = ""
        self.counter = 0
        self.start_bit = False
        self.start_add = None        
        self.start_btn = None
        self.start_ant = None
        self.start_digit = None
        self.end_digit = None
        
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.initial_pins = [0]

    def decode(self):
        add_size = self.options['add_size']
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        while True:
            pin = self.wait({0: 'e'})

            if self.oldpin is None:
                self.oldpin = pin
                self.last_samplenum = self.samplenum
                continue
           
            if self.oldpin != pin:
                samples = self.samplenum - self.last_samplenum
                pulse_width = samples / self.samplerate    
                if (pin[0]) == 0:
                    pulse_value = 1
                else:
                    pulse_value = 0 
               
                if(self.start_bit == False):
                    if (pulse_width>0.0092 and pulse_width < 0.0138 and pulse_value==0):
                        lada = float(pulse_width)/23                       
                        self.put(self.last_samplenum, self.samplenum, self.out_ann, [0, [normalize_time(pulse_width)]]) 
                        self.put(self.last_samplenum, self.samplenum, self.out_ann, [1, ["Pilot"]])
                        self.put(self.last_samplenum, self.samplenum, self.out_ann, [2, ["Lambda = %s"  % (normalize_time(lada))]])
                        self.start_add = self.samplenum
                        self.end_digit = self.samplenum
                        if pulse_width > (4 * lada):
                            self.start_bit = True
                        else: 
                            self.start_bit = False
                        self.counter = 0
                        self.buff = ""
                if(self.start_bit == True and self.counter < 29):                    
                    if (pulse_value==1): 
                        if self.counter > 0:
                            self.start_digit = self.end_digit
                            self.end_digit = self.samplenum
                            
                            if((pulse_width > (0.5)*lada) and (pulse_width<(1.5*lada))):
                                if self.counter <= add_size:
                                    self.buff+="1"
                                self.put(self.start_digit, self.end_digit, self.out_ann, [1, ["1"]])
                            elif((pulse_width > (1.5)*lada) and (pulse_width<(2.5*lada))):
                                if self.counter <= add_size:
                                    self.buff+="0"
                                self.put(self.start_digit, self.end_digit, self.out_ann, [1, ["0"]])        
                            else:
                                self.start_bit = False
                                
                            
                                
                            if self.counter == add_size:
                                self.start_btn = self.samplenum
                                self.put(self.start_add, self.start_btn, self.out_ann, [2, ["ADDRESS %s, len=%d" % (hex(int(self.buff, 2)),len(self.buff))]])
                            elif self.counter == 24:
                                self.start_ant = self.samplenum
                                self.put(self.start_btn, self.start_ant, self.out_ann, [2, ["BTN"]])     
                        self.counter += 1    
                   
                                          
                if (self.counter==29):
                    self.counter = 0
                    self.start_bit = False
                    self.put(self.start_ant, self.samplenum, self.out_ann, [2, ["ANTI"]])     
                    
                    
                    
                    
                # Store data for next round.
                self.last_samplenum = self.samplenum
                self.oldpin = pin