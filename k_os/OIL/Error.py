 # -*- coding: utf-8 -*-

__version__="0.9.0"

__copyright__="""
   k_os (Konnex Operating-System based on the OSEK/VDX-Standard).

   (C) 2007-2011 by Christoph Schueler <github.com/Christoph2,
                                        cpu12.gems@googlemail.com>

   All Rights Reserved

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License along
  with this program; if not, write to the Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

   s. FLOSS-EXCEPTION.txt
"""

import logging
import sys

def createLogger(level,name,fmt):
    logger=logging.getLogger(name)
    logger.setLevel(level)
    ch=logging.StreamHandler()
    ch.setLevel(level)
    formatter=logging.Formatter(fmt)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

class OILError(object):
    inst=None

    def __new__(cls):
        if cls.inst is None:
            # Make it a Singleton.
            cls.inst=super(OILError,cls).__new__(cls)
            cls.fatalErrorCounter=0
            cls.errorCounter=0
            cls.warningCounter=0
            cls.informationCounter=0

            cls.loggerMessageonly=createLogger(logging.NOTSET,"kos.oil.logger.messageonly",
                "[%(levelname)s] - %(message)s"
            )
            cls.loggerFilename=createLogger(logging.NOTSET,"kos.oil.logger.filename",
                "[%(levelname)s]:%(fname)s - %(message)s"
            )
            cls.loggerFull=createLogger(logging.NOTSET,"kos.oil.logger.full",
                 "[%(levelname)s]:%(fname)s:%(lno)s - %(message)s"
            )
        return cls.inst

    def logMessage(self,level,message,lineno=None,filename=None,code=None):
        if lineno and filename:
            self.loggerFull.log(level,message,extra={'lno': lineno,'fname': filename})
        elif filename:
            self.loggerFilename.log(level,message,extra={'fname': filename})
        else:
            self.loggerMessageonly.log(level,message)


    def fatalError(self,message,lineno=None,filename=None,code=''):
        self.logMessage(logging.CRITICAL,message,lineno,filename,"F-"+code)
        self.fatalErrorCounter+=1
        sys.exit(1)

    def error(self,message,lineno=None,filename=None,code=''):
        self.logMessage(logging.ERROR,message,lineno,filename,"E-"+code)
        self.errorCounter+=1

    def warning(self,message,lineno=None,filename=None,code=''):
        self.logMessage(logging.WARNING,message,lineno,filename,"W-"+code)
        self.warningCounter+=1

    def information(self,message,lineno=None,filename=None,code=''):
        self.logMessage(logging.INFO,message,lineno,filename,"I-"+code)
        self.informationCounter+=1

