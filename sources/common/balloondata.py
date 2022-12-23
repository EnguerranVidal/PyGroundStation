import dataclasses
import json
import os
import csv
import shutil
from enum import Enum
from typing import Any, Optional, Type

from ecom.database import CommunicationDatabase, CommunicationDatabaseError, Unit, ConfigurationValueResponse, \
    ConfigurationValueArgument, Configuration, Telecommand
from ecom.datatypes import TypeInfo, StructType
from ecom.parser import TelemetryResponse, TelemetryResponseType


class BalloonPackageDatabase(CommunicationDatabase):
    """ The shared communication database for balloon packages. Contains all information about the telecommunication.
    """

    def __eq__(self, other: CommunicationDatabase):
        print('----')
        print(self._units == other.units)
        print(self._constants == other.constants)
        print(self._typeMapping == other.dataTypes)
        print(self._telecommands == other.telecommands)
        print(self._telemetryTypes == other.telemetryTypes)
        print(self._configurations == other.configurations)
        print('----')

        return isinstance(other, CommunicationDatabase) and \
            self._units == other.units and \
            self._constants == other.constants and \
            self._typeMapping == other.dataTypes and \
            self._telecommands == other.telecommands and \
            self._telemetryTypes == other.telemetryTypes and \
            self._configurations == other.configurations

    def save(self, dataDirectory):
        try:
            shutil.rmtree(dataDirectory)
        except FileNotFoundError:
            pass
        os.makedirs(dataDirectory, exist_ok=True)
        self._saveUnits(os.path.join(dataDirectory, 'units.csv'))
        self._saveConstants(os.path.join(dataDirectory, 'sharedConstants.csv'))
        self._saveConfigurations(os.path.join(dataDirectory, 'configuration.csv'))
        self._saveTelemetry(os.path.join(dataDirectory, 'telemetry.csv'))
        self._saveTelemetryArguments(os.path.join(dataDirectory, 'telemetryArguments'))
        self._saveTypes(os.path.join(dataDirectory, 'sharedDataTypes.json'))

        self._saveTelecommands(os.path.join(dataDirectory, 'commands.csv'))
        self._saveTelecommandArguments(os.path.join(dataDirectory, 'commandArguments'))

    def _saveTypes(self, typesFilePath):
        """
        Saves the shared datatype information.

        :param typesFilePath: The path to the shared data types file.
        """
        types = {}
        autogeneratedTypes = [
            'ConfigurationId',
            'Configuration',
            'Telecommand',
            'TelemetryType',
        ]
        for name, typInfo in self.dataTypes.items():
            if name not in autogeneratedTypes:
                types[name] = self._serializeType(typInfo)
        with open(typesFilePath, 'w', encoding='utf-8') as outputFile:
            json.dump(types, outputFile, indent=2, ensure_ascii=True)

    def _serializeType(self, typeInfo: TypeInfo):
        serializedType = {}
        self._serializeBasicTypeInfo(serializedType, typeInfo)
        if issubclass(typeInfo.type, Enum):  # Enumerations
            serializedType['__type__'] = typeInfo.baseTypeName
            if all(not child.__doc__ for child in typeInfo.type):
                values = [enumValue.name for enumValue in typeInfo.type]
            else:
                values = {
                    enumValue.name: {'__doc__': enumValue.__doc__}
                    for enumValue in typeInfo.type
                }
            serializedType['__values__'] = values
        elif issubclass(typeInfo.type, StructType):  # Structures
            for name, child in typeInfo.type:
                if child.baseTypeName not in self.dataTypes:
                    serializedType[name] = self._serializeType(child)
                else:
                    serializedChild = {}
                    self._serializeBasicTypeInfo(serializedChild, child)
                    if not serializedChild:  # Simple case
                        serializedChild = child.baseTypeName
                    else:
                        serializedChild['__type__'] = child.baseTypeName
                    serializedType[name] = serializedChild
        else:  # Others
            if not serializedType:  # Simple case
                return typeInfo.baseTypeName
            serializedType['__type__'] = typeInfo.baseTypeName
        return serializedType

    @staticmethod
    def _serializeBasicTypeInfo(serializedType, typeInfo):
        if typeInfo.description:
            serializedType['__doc__'] = typeInfo.description
        if typeInfo.default is not None:
            serializedType['__value__'] = typeInfo.default.constantName \
                if typeInfo.default.constantName is not None else typeInfo.default.value

    def _saveConstants(self, sharedConstantsFilePath):
        """
        Saves the shared constants.

        :param sharedConstantsFilePath: The path to the shared constants file.
        """
        autogeneratedConstantNames = [
            'NUM_CONFIGURATIONS',
            'DEFAULT_CONFIGURATION',
            'MAX_TELECOMMAND_DATA_SIZE',
            'MAX_TELECOMMAND_RESPONSE_SIZE',
        ]
        if not self.constants:
            return
        try:
            with open(sharedConstantsFilePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Value', 'Type', 'Description'])
                for constantName, constant in self.constants.items():
                    if constantName not in autogeneratedConstantNames:
                        csvWriter.writerow([constantName, constant[0], constant[2].baseTypeName, constant[1]])
        except IOError as error:
            raise CommunicationDatabaseError(f'Error writing {sharedConstantsFilePath}: {error}')

    def _saveConfigurations(self, configurationsFilePath):
        """
        Saves the secondary device configuration items.

        :param configurationsFilePath: The path to the configurations file.
        """
        if not self.configurations:
            return
        try:
            with open(configurationsFilePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Type', 'Default Value', 'Description'])
                for configuration in self.configurations:
                    csvWriter.writerow([configuration.name, self._getTypeName(configuration.type),
                                        json.dumps(configuration.defaultValue), configuration.description])
        except IOError as error:
            raise CommunicationDatabaseError(f'Error writing {configurationsFilePath}: {error}')

    def _saveUnits(self, unitsFilePath):
        """
        Saves the unit types.

        :param unitsFilePath: The path to the units file.
        """
        if not self.units:
            return
        try:
            with open(unitsFilePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Type', 'Description'])
                for unitName, unitVariants in self.units.items():
                    unit = unitVariants[0]
                    csvWriter.writerow([unit.name, unit.baseTypeName, unit.description])
        except IOError as error:
            raise CommunicationDatabaseError(f'Error writing {unitsFilePath}: {error}')

    def _saveTelecommands(self, telecommandsFilePath):
        """
        Saves the telecommands.

        :param telecommandsFilePath: The path to the file containing information about the telecommands.
        """
        if not self.telecommands:
            return
        try:
            with open(telecommandsFilePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Debug', 'Description', 'Response name',
                                    'Response type', 'Response description'])
                for telecommand in self.telecommands:
                    responseName, responseType, responseDescription = '', '', ''
                    if telecommand.response:
                        responseName = telecommand.response.name
                        responseDescription = telecommand.response.description
                        if isinstance(telecommand.response, ConfigurationValueResponse):
                            responseType = 'config?'
                        else:
                            responseType = self._getTypeName(telecommand.response.typeInfo)
                    csvWriter.writerow([telecommand.name, str(telecommand.isDebug).lower(), telecommand.description,
                                        responseName, responseType, responseDescription])
        except IOError as error:
            raise CommunicationDatabaseError(f'Error writing {telecommandsFilePath}: {error}')

    def _saveTelecommandArguments(self, telecommandsArgumentsFolder):
        """
        Saves the arguments for the telecommands.

        :param telecommandsArgumentsFolder: The path to the folder containing the files where the telecommand
                                            arguments information is to be saved.
        """
        os.makedirs(telecommandsArgumentsFolder, exist_ok=True)
        for telecommand in self.telecommands:
            filePath = os.path.join(telecommandsArgumentsFolder, telecommand.name + '.csv')
            if not telecommand.arguments:
                continue
            with open(filePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Type', 'Default', 'Description'])
                for argument in telecommand.arguments:
                    if isinstance(argument, ConfigurationValueArgument):
                        dataPointType = 'config?'
                    else:
                        dataPointType = self._getTypeName(argument.typeInfo)
                    default = '' if argument.default is None else json.dumps(argument.default)
                    csvWriter.writerow([argument.name, dataPointType, default, argument.description])

    def _saveTelemetry(self, telemetriesFilePath):
        """
        Saves the telemetry types.

        :param telemetriesFilePath: The path to the file containing information about the telemetry.
        """
        if not self.telemetryTypes:
            return
        try:
            with open(telemetriesFilePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Description'])
                for telemetryResponseType in self.telemetryTypes:
                    csvWriter.writerow([telemetryResponseType.id.name, telemetryResponseType.id.__doc__])
        except IOError as error:
            raise CommunicationDatabaseError(f'Error writing {telemetriesFilePath}: {error}')

    def _saveTelemetryArguments(self, telemetryArgumentsFolder):
        """
        Saves the arguments for the telemetry types.

        :param telemetryArgumentsFolder: The path to the folder containing the files where the telemetry
                                         arguments information is going to be saved.
        """
        os.makedirs(telemetryArgumentsFolder, exist_ok=True)
        for telemetryResponseType in self.telemetryTypes:
            if not telemetryResponseType.data:
                continue
            filePath = os.path.join(telemetryArgumentsFolder, telemetryResponseType.id.name + '.csv')
            with open(filePath, "w", newline='', encoding='utf-8') as file:
                csvWriter = csv.writer(file)
                csvWriter.writerow(['Name', 'Type', 'Description'])
                for dataPoint in telemetryResponseType.data:
                    dataPointType = self._getTypeName(dataPoint.type)
                    csvWriter.writerow([dataPoint.name, dataPointType, dataPoint.description])

    def _getTypeName(self, typeInfo):
        typeName = typeInfo.name
        try:
            if isinstance(typeInfo, Unit) and self.units[typeName][0].baseTypeName != typeInfo.baseTypeName:
                typeName = f'{typeInfo.baseTypeName} ({typeName})'
        except KeyError:
            # Unit does not exist anymore : not searching for variants
            pass
        return typeName

    def getTypeName(self, typeInfo):
        return self._getTypeName(typeInfo)

    def addConfiguration(self, name: str, replaceIndex: Optional[int] = None,  **kwargs):
        self._configurations = self._editElement(
            name, self._configurations, Configuration, replaceIndex=replaceIndex, **kwargs)

    def addTelecommand(self, name: str, replaceIndex: Optional[int] = None,  **kwargs):
        self._telecommands = self._editElement(
            name, self._telecommands, Telecommand, replaceIndex=replaceIndex, **kwargs)

    def editTelemetry(self, name: str, replaceIndex: Optional[int] = None,  **kwargs):
        self._telemetryTypes = self._editElement(
            name, self._telemetryTypes, TelemetryResponseType, replaceIndex=replaceIndex, **kwargs)

    @staticmethod
    def _editElement(name: str, elements, typeClass, replaceIndex: Optional[int] = None, **kwargs):
        for element in elements:
            elementEnum = element.id.__class__  # type: Type[Enum]
            break
        else:
            return
        existingEnumNames = [config.name for config in elementEnum]
        existingEnumNames.append(name)
        elementEnum = Enum(elementEnum.__name__, existingEnumNames, start=0)
        newElements = [
            dataclasses.replace(element, id=elementId)
            for element, elementId in zip(elements, elementEnum)
        ]
        newElement = typeClass(
            id=elementEnum[name],
            name=name,
            **kwargs,
        )
        if replaceIndex is None:
            newElements.append(newElement)
        else:
            newElements[replaceIndex] = newElement
        return newElements
