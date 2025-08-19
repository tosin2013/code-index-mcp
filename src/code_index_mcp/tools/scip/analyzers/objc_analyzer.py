"""
Objective-C language-specific SCIP symbol analyzer.

This module handles Objective-C specific logic extracted from the monolithic
SCIPSymbolAnalyzer, including framework detection and system library classification.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from .base import BaseLanguageAnalyzer
from ..symbol_definitions import ImportGroup

logger = logging.getLogger(__name__)


class ObjectiveCAnalyzer(BaseLanguageAnalyzer):
    """
    Objective-C language-specific SCIP symbol analyzer.

    Handles Objective-C specific framework imports, system library detection,
    and symbol metadata extraction.
    """

    def _get_language_name(self) -> str:
        return "objective-c"

    def _build_standard_library_modules(self) -> Set[str]:
        """Build comprehensive Objective-C system frameworks set."""
        return {
            # Core frameworks (iOS and macOS)
            'Foundation', 'CoreFoundation', 'CoreData', 'CoreGraphics',
            'QuartzCore', 'CoreAnimation', 'CoreImage', 'CoreText',
            'Security', 'SystemConfiguration', 'CFNetwork',

            # UI frameworks
            'UIKit', 'AppKit', 'Cocoa', 'SwiftUI',

            # Media frameworks
            'AVFoundation', 'AVKit', 'AudioToolbox', 'AudioUnit',
            'VideoToolbox', 'MediaPlayer', 'Photos', 'PhotosUI',
            'CoreAudio', 'CoreMIDI', 'CoreMedia', 'ImageIO',

            # Graphics and gaming
            'Metal', 'MetalKit', 'GameplayKit', 'SpriteKit', 'SceneKit',
            'GLKit', 'OpenGLES', 'CoreMotion', 'ARKit', 'RealityKit',

            # Location and maps
            'CoreLocation', 'MapKit', 'Contacts', 'ContactsUI',

            # Web and networking
            'WebKit', 'JavaScriptCore', 'NetworkExtension',

            # Data and storage
            'CloudKit', 'CoreSpotlight', 'EventKit', 'EventKitUI',
            'HealthKit', 'HealthKitUI', 'HomeKit', 'HomeKitUI',

            # Device and sensors
            'CoreBluetooth', 'ExternalAccessory', 'CoreNFC',
            'CoreTelephony', 'CallKit', 'PushKit',

            # Machine learning and AI
            'CoreML', 'Vision', 'NaturalLanguage', 'Speech',
            'SoundAnalysis',

            # Development tools
            'XCTest', 'os', 'Accelerate', 'simd',

            # Legacy frameworks
            'AddressBook', 'AddressBookUI', 'AssetsLibrary',
            'MobileCoreServices', 'Social', 'Accounts',

            # watchOS specific
            'WatchKit', 'ClockKit', 'WatchConnectivity',

            # tvOS specific
            'TVUIKit', 'TVMLKit',

            # macOS specific
            'Carbon', 'ApplicationServices', 'CoreServices',
            'IOKit', 'DiskArbitration', 'FSEvents', 'ServiceManagement',
            'LaunchServices', 'SearchKit', 'PreferencePanes',
            'InstantMessage', 'Automator', 'CalendarStore',
            'Collaboration', 'CoreWLAN', 'DiscRecording',
            'DiscRecordingUI', 'DVDPlayback', 'ExceptionHandling',
            'FWAUserLib', 'InstallerPlugins', 'IOBluetooth',
            'IOBluetoothUI', 'Kernel', 'LDAP', 'Message',
            'OpenDirectory', 'OSAKit', 'PubSub', 'QTKit',
            'Quartz', 'QuartzComposer', 'QuickLook', 'ScreenSaver',
            'ScriptingBridge', 'SyncServices', 'Tcl', 'Tk',
            'WebKit', 'XgridFoundation'
        }

    def _classify_dependency_impl(self, module_name: str) -> str:
        """
        Classify Objective-C dependency based on framework patterns.

        Args:
            module_name: Framework/module name to classify

        Returns:
            Classification: 'standard_library', 'third_party', or 'local'
        """
        # Local imports (project-specific)
        if any(pattern in module_name for pattern in ['.', '/', 'Private', 'Internal']):
            return 'local'

        # System frameworks check
        if module_name in self.get_standard_library_modules():
            return 'standard_library'

        # Third-party framework indicators
        third_party_indicators = {
            'AFNetworking', 'Alamofire', 'SDWebImage', 'MBProgressHUD',
            'JSONModel', 'RestKit', 'Firebase', 'ReactiveCocoa',
            'Masonry', 'SnapKit', 'Realm', 'FMDB', 'SQLite',
            'GoogleAnalytics', 'Fabric', 'Crashlytics', 'TestFlight',
            'Facebook', 'Twitter', 'Instagram', 'Pods'
        }

        for indicator in third_party_indicators:
            if indicator in module_name:
                return 'third_party'

        # CocoaPods/Carthage patterns
        if any(pattern in module_name for pattern in ['Pod', 'Carthage', 'SPM']):
            return 'third_party'

        # Default to standard_library for unknown frameworks
        # (Objective-C tends to have many system frameworks)
        return 'standard_library'

    def extract_imports(self, document, imports: ImportGroup, symbol_parser=None) -> None:
        """
        Extract Objective-C imports from SCIP document.

        Args:
            document: SCIP document containing symbols and occurrences
            imports: ImportGroup to populate with extracted imports
            symbol_parser: Optional SCIPSymbolManager for enhanced parsing
        """
        try:
            seen_modules = set()

            # Method 1: Extract from occurrences with Import role
            if symbol_parser:
                for occurrence in document.occurrences:
                    if not self.is_import_occurrence(occurrence):
                        continue

                    symbol_info = symbol_parser.parse_symbol(occurrence.symbol)
                    if not symbol_info:
                        continue

                    # Handle based on manager type
                    if symbol_info.manager in ['system', 'framework']:
                        framework_name = symbol_info.package or self._extract_framework_from_descriptors(symbol_info.descriptors)
                        if framework_name and framework_name not in seen_modules:
                            imports.add_import(framework_name, 'standard_library')
                            seen_modules.add(framework_name)

                    elif symbol_info.manager in ['cocoapods', 'carthage', 'third_party']:
                        package_name = symbol_info.package or self._extract_framework_from_descriptors(symbol_info.descriptors)
                        if package_name and package_name not in seen_modules:
                            imports.add_import(package_name, 'third_party')
                            seen_modules.add(package_name)

                    elif symbol_info.manager == 'local':
                        module_path = self._extract_local_module_path(symbol_info.descriptors)
                        if module_path and module_path not in seen_modules:
                            imports.add_import(module_path, 'local')
                            seen_modules.add(module_path)

            # Method 2: Extract from external symbols (if available in index)
            # This handles frameworks detected during indexing but not in occurrences
            self._extract_from_external_symbols_if_available(imports, seen_modules, symbol_parser)

            logger.debug(f"Extracted {len(seen_modules)} Objective-C imports/frameworks")

        except Exception as e:
            logger.debug(f"Error extracting Objective-C imports: {e}")

    def _extract_symbol_metadata_impl(self, symbol_info, document) -> Dict[str, Any]:
        """
        Extract Objective-C specific symbol metadata.

        Args:
            symbol_info: SCIP symbol information
            document: SCIP document

        Returns:
            Dictionary with Objective-C specific metadata
        """
        metadata = {
            'language': 'objective-c',
            'source': 'objc_analyzer'
        }

        try:
            # Extract method signature patterns
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                signature = symbol_info.signature
                metadata['signature'] = signature

                # Parse Objective-C method patterns
                if signature.startswith('-') or signature.startswith('+'):
                    metadata['is_method'] = True
                    metadata['is_instance_method'] = signature.startswith('-')
                    metadata['is_class_method'] = signature.startswith('+')

                # Parse method parameters (Objective-C style)
                if ':' in signature:
                    metadata['parameter_count'] = signature.count(':')
                    metadata['method_labels'] = self._extract_method_labels(signature)

                # Parse return type
                if ')' in signature and '(' in signature:
                    return_type_match = signature.split(')')
                    if len(return_type_match) > 0:
                        return_type = return_type_match[0].strip('(+-')
                        if return_type:
                            metadata['return_type'] = return_type

            # Extract property characteristics
            symbol = getattr(symbol_info, 'symbol', '')
            if symbol:
                metadata['is_property'] = self._is_objc_property(symbol)
                metadata['is_protocol'] = self._is_objc_protocol(symbol)
                metadata['is_category'] = self._is_objc_category(symbol)
                metadata['framework'] = self._extract_framework_from_symbol(symbol)

            # Extract documentation
            if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
                metadata['documentation'] = symbol_info.documentation

        except Exception as e:
            logger.debug(f"Error extracting Objective-C metadata: {e}")
            metadata['extraction_error'] = str(e)

        return metadata

    def _extract_framework_from_descriptors(self, descriptors: str) -> Optional[str]:
        """
        Extract framework name from SCIP descriptors for Objective-C.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Framework name or None
        """
        try:
            # Handle descriptors like 'Foundation/' or 'UIKit/UIView'
            if '/' in descriptors:
                return descriptors.split('/')[0]
            return descriptors.strip('/')
        except Exception:
            return None

    def _extract_local_module_path(self, descriptors: str) -> Optional[str]:
        """
        Extract local module path from descriptors for Objective-C.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Module path or None
        """
        try:
            # Handle local Objective-C files
            if '/' in descriptors:
                parts = descriptors.split('/')
                if len(parts) >= 2:
                    file_part = parts[0]
                    if file_part.endswith('.h') or file_part.endswith('.m'):
                        return file_part
                    return file_part
            return None
        except Exception:
            return None

    def _extract_from_external_symbols_if_available(self, imports: ImportGroup, seen_modules: Set[str], symbol_parser) -> None:
        """
        Extract additional imports from external symbols if available.
        This method would be called with the full SCIP index if available.
        """
        # This method would need to be integrated with the main analyzer
        # to access external symbols from the SCIP index
        pass

    def _extract_method_labels(self, signature: str) -> List[str]:
        """
        Extract Objective-C method labels from signature.

        Args:
            signature: Method signature string

        Returns:
            List of method labels
        """
        try:
            # Parse Objective-C method signature like: "-(void)setName:(NSString*)name withAge:(int)age"
            labels = []
            parts = signature.split(':')
            for part in parts[:-1]:  # Exclude last part after final :
                # Extract the label (word before the colon)
                words = part.strip().split()
                if words:
                    label = words[-1]
                    if label and not label.startswith('(') and not label.startswith('-') and not label.startswith('+'):
                        labels.append(label)
            return labels
        except Exception:
            return []

    def _is_objc_property(self, symbol: str) -> bool:
        """Check if symbol represents an Objective-C property."""
        try:
            # Properties often have specific patterns in SCIP symbols
            return '@property' in symbol or 'property' in symbol.lower()
        except Exception:
            return False

    def _is_objc_protocol(self, symbol: str) -> bool:
        """Check if symbol represents an Objective-C protocol."""
        try:
            return '@protocol' in symbol or 'protocol' in symbol.lower()
        except Exception:
            return False

    def _is_objc_category(self, symbol: str) -> bool:
        """Check if symbol represents an Objective-C category."""
        try:
            # Categories often have + in their symbol representation
            return '(' in symbol and ')' in symbol
        except Exception:
            return False

    def _extract_framework_from_symbol(self, symbol: str) -> Optional[str]:
        """
        Extract framework name from SCIP symbol string.

        Args:
            symbol: SCIP symbol string

        Returns:
            Framework name or None
        """
        try:
            # Handle various SCIP symbol formats for frameworks
            if 'Foundation' in symbol:
                return 'Foundation'
            elif 'UIKit' in symbol:
                return 'UIKit'
            # Add more specific framework detection as needed

            # Generic extraction from symbol structure
            if ' ' in symbol:
                parts = symbol.split()
                for part in parts:
                    if part in self.get_standard_library_modules():
                        return part

            return None
        except Exception:
            return None
