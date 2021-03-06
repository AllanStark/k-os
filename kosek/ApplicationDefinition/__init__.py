#!/usr/bin/python
# -*- coding: utf-8 -*-

__version__ = '0.9.2rc-1'
__copyright__ = """
   k_os (Konnex Operating-System based on the OSEK/VDX-Standard).

   (C) 2007-2014 by Christoph Schueler <github.com/Christoph2,
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

from collections import defaultdict
import unittest

from kosek.Logger import Logger
from kosek.ApplicationDefinition.Parameter import Parameter, ParameterList
from kosek.ApplicationDefinition.AttributeValueContainter import AttributeValueContainter, typeFromImplementationAttribute
from kosek.ApplicationDefinition.ParameterContainer import ParameterContainer, NestedParameter
from kosek.ImplementationDefinition import ImplAttrType, AttributeDefinitionFactory, ImplRefDef

logger = Logger()

class Info(object): pass


class ApplicationDefinitionBuilder(object):
    def __init__(self, parser, definitionList, description):
        self.definitionList = definitionList
        self.parser = parser
        self.description = description
        self.info = Info()

    def postProcessing(self):
        self.standardResources = self.parser.standardResources
        self.internalResources = self.parser.internalResources
        self.linkedResources = self.parser.linkedResources
        self.internalMessages = self.parser.internalMessages
        self.externalMessages = self.parser.externalMessages
        self.autostartedTasks = self.getAutostartedObjects('TASK')
        self.autostartedAlarms = self.getAutostartedObjects('ALARM')
        self.setTaskFlags()
        self.calculatePriorities()
        self.calculateCeilingPriorities()

    def getObjects(self, objectType):
        return [v for k, v in self.definitionList.items() if k == objectType][0]

    def getAutostartedObjects(self, objectType):
        result = []
        # Filter nur vor�bergehend - AUTOSTART ist nicht optional!!!
        objs = [v for _, v in self.getObjects(objectType).items() if v.hasAutostarts]
        for obj in objs:
            if obj.AUTOSTART.value == True:
                result.append(obj)
            elif isinstance(obj.AUTOSTART, NestedParameter) and obj.AUTOSTART.value:
                result.append(obj)
        return result

    def setTaskFlags(self):
        for (_, task) in self.getObjects('TASK').items():
            flags = []
            if 'EVENT' in task.parameters:
                flags.append('OS_TASK_ATTR_EXTENDED')
            schedule = task.SCHEDULE.value
            if schedule == "FULL":
                flags.append('OS_TASK_ATTR_FULLPREEMPT')
            if flags:
                task.flags = ' | '.join(flags)
            else:
                task.flags = '((uint8)0)'   # TODO: Sinnvolle Konstante!!!

    def calculateCeilingPriorities(self):
        usedResources = {}
        resources = dict(self.getObjects('RESOURCE').items())

        for _, task in self.getObjects('TASK').items():
            if hasattr(task, 'RESOURCE'):
                for resource in task.RESOURCE:
                    usedResources.setdefault(resource.value, []).append(task)
        for resourceName, tasks in usedResources.items():
            try:
                resources[resourceName].relativeCeilingPriority = max([t.ABSOLUTE_PRIORITY for t in tasks])
            except KeyError:
                print "Undefined resource '%s'." % resourceName

        for idx, (_, alarm) in enumerate(self.getObjects('ALARM').items()):
            alarm.pos = idx

    def calculatePriorities(self):
        eCCx = False
        xCC2 = False
        self.info.priorities = dict()
        tasks = self.getObjects('TASK')

        os = self.getObjects('OS').values()[0]
        ortiD = os.ORTI_DEBUG.KOIL_VERSION.value

        self.info.numberOfPreemtiveTasks = 0
        self.info.numberOfNonPreemtiveTasks = 0
        for _, task in tasks.items():
            schedule = task.SCHEDULE.value
            priority = task.PRIORITY.value
            if schedule == 'FULL':
                self.info.numberOfPreemtiveTasks += 1
            else:
                self.info.numberOfNonPreemtiveTasks += 1
            self.info.priorities.setdefault(priority, []).append(task)
        self.info.numberOfDistinctPriorities = len(self.info.priorities.keys())
        priorityMap = dict()
        for (idx, objects) in enumerate(self.info.priorities.values(), 1):
            if len(objects) > 1:
                xCC2 = True
            levelPriority = objects[0].PRIORITY.value
            activations = 0
            for obj in objects:
                activationsForObject = obj.ACTIVATION.value
                obj.ABSOLUTE_PRIORITY = idx
                activations += activationsForObject
            priorityMap[levelPriority] = (idx, activations)
        self.info.priorityMap = priorityMap


class ValueDescriptionPair(object):
    def __init__(self, value, description):
        self._value = value
        self._description = description

    @property
    def value(self):
        return self._value

    @property
    def description(self):
        return self._description

    def __repr__(self):
        if self.description:
            return 'VALUE(%s : "%s")' % (self.value, self.description)
        else:
            return 'VALUE(%s)' % (self.value, )


class ObjectDefinition(ParameterContainer):
    def __init__(self, parser, objectType, name, parameterList, description):
        self.parser = parser
        self.implDefinition = self.parser.implDefinition[objectType]
        self.parameters = {}
        self.setValues(objectType, name, parameterList, description)
        self._hasAutostarts = False

    def setDefaultAttr(self, attr, value):
        if not hasattr(self, attr):
            setattr(self, attr, value)

    def setValues(self, objectType, name, parameterList, description):
        self.setDefaultAttr('objectType', objectType)
        self.setDefaultAttr('implDefinition', self.parser.implDefinition[objectType])
        self.setDefaultAttr('name', name)
        self.description = description or ''
        if parameterList:
            self.parameters.update({p[0]: p[1] for p in parameterList.grouped()})
# http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/latest/exports/Msp430GCCopensource-msp430-130423-371-windows-installer.exe
        if objectType == 'TASK':
            self._taskType = 'EXTENDED' if 'EVENT' in self.parameters else 'BASIC'
            self._hasResources = True if 'RESOURCE'  in self.parameters else False
            self._hasEvents = True if 'EVENT' in self.parameters else False
            self._hasAutostarts = True if 'AUTOSTART' in self.parameters  else False
        elif objectType == 'ALARAM':
            self._hasAutostarts = True if 'AUTOSTART'  in self.parameters else False
        elif objectType == 'RESOURCE':
            resourceProperty = self.RESOURCEPROPERTY.value
            if resourceProperty == 'STANDARD':
                self.parser.standardResources.append(self)
            elif resourceProperty == 'INTERNAL':
                self.parser.internalResources.append(self)
            elif resourceProperty == 'LINKED':
                self.parser.linkedResources.append(self)
        elif objectType == 'EVENT':
            pass
        elif objectType == 'MESSAGE':
            if 'INTERNAL' in self.MESSAGEPROPERTY.value:
                self.parser.internalMessages.append(self)
            else:
                self.parser.externalMessages.append(self)

    def appendValues(self, objectType, name, parameterList, description):
        ## TODO: Warning/Error wenn vorhandene Werte �berschrieben werden sollen!!!
        self.setValues(objectType, name, parameterList, description)
        return self

    def __getattr__(self, attr):
        if attr in self.parameters:
            param = self.parameters[attr]
            implDef = self.implDefinition[attr]
            if implDef.mult == True:
                 return [p.parameterValue for p in param]
            else:
                return param[0].parameterValue
        else:
            raise AttributeError(attr)

    @property
    def taskType(self):
        return self._taskType

    @property
    def hasResources(self):
        return self._hasResources

    @property
    def hasEvents(self):
        return self._hasEvents

    @property
    def hasAutostarts(self):
        return self._hasAutostarts


class ObjectDefinitionList(object):
    def __init__(self, parser, definitionList):
        self.definitionList = definitionList
        self.parser = parser

    def run(self):
        implDefinition = self.parser.implDefinition
        result = {}
        autos = {}
        for definition in self.definitionList:
            result.setdefault(definition.objectType, {})[definition.name ] = definition
            #print "DEF: %s::%s" % (definition.objectType, definition.name)
            implDefinitionForObject = implDefinition[definition.objectType]
            actualParameters = set(definition.parameters.keys())
            if isinstance(definition, ImplRefDef):
                defaultParameters = set()
            else:
                defaultParameters = set([key for key, value in definition.implDefinition.items() if not isinstance(value, ImplRefDef) and value.default])
                nonDefaultParameters = set([key for key, value in definition.implDefinition.items() if not isinstance(value, ImplRefDef) and not value.default])

            defaultsNeeded = defaultParameters - actualParameters
            nonDefaultsNeeded = nonDefaultParameters - actualParameters

            for default in defaultsNeeded:
                flonza = AttributeValueContainter(typeFromImplementationAttribute(
                    implDefinitionForObject[default].dataType),
                    **{default: implDefinitionForObject[default].default}
                )

                setattr(definition, default, flonza)
            #print "*** '%s::%s' needs the following default parameters: '%s'." % (definition.objectType, definition.name , defaultsNeeded)

            for parameterName, parameterValue in definition.parameters.items():
                if parameterName == 'RESOURCE':
                    pass
                if parameterName == 'ISR_STACK_SIZE':
                    pass
                implParameterDefinition = implDefinitionForObject[parameterName]
                ## TODO: Handle invalid attributes!!!
                #parameter.implDefinition = implParameterDefinition
                #print "DEF: %s::%s.%s" % (definition.objectType, definition.name, parameterName)
                if parameterValue == 'AUTO':
                    autos[(definition.objectType, definition.name, parameterName)] = (
                        parameter, implParameterDefinition
                    )
            path = []
            self.validate(definition, implDefinition[definition.objectType], path)
        return result

    def validate(self, definition, implDefinitionDict, path):
        ##
        ## TODO: Überarbeiten!!!
        ##
        path.append("Validate: [%s]%s" % (definition.objectType, definition.name))

        #for _, group in definition.parameterList.grouped():    # Validate multiplicities.
        #    sz = len(group)
        #    if sz > 1:
        #        pass

        #for parameter in definition.parameterList:  # Validate individual parameters.
        #    parameterValue = parameter.parameterValue.value
        #    parameterName = parameter.parameterName
        #    implDefinition = implDefinitionDict[parameterName]
        #
        #    implDefinition.validate(parameter, path)

    def setDefaults(self, parameter):
        ImplRefDef = {}

        actualParameters = set([p.parameterName for p in parameter.parameterList])
        if isinstance(parameter, ImplRefDef):
            defaultParameters = set()
        else:
            defaultParameters = set([key for key, value in parameter.implDefinition.items() if not isinstance(value, ImplRefDef) and value.default])

        defaultsNeeded = defaultParameters - actualParameters

