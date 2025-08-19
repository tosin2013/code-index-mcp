"""
Objective-C-specific dependency configuration.

This module provides Objective-C specific dependency classification,
including iOS/macOS framework detection and CocoaPods support.
"""

import re
import logging
from typing import Set, Dict, List, Optional
from .base import BaseDependencyConfig

logger = logging.getLogger(__name__)


class ObjectiveCDependencyConfig(BaseDependencyConfig):
    """
    Objective-C-specific dependency configuration.

    Handles Objective-C framework and dependency classification with support for:
    - iOS and macOS system frameworks
    - CocoaPods package management
    - Carthage dependency management
    - Swift Package Manager integration
    - Private framework detection
    """

    def get_language_name(self) -> str:
        return "objective-c"

    def get_stdlib_modules(self) -> Set[str]:
        """Return iOS/macOS system frameworks."""
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

    def _compile_patterns(self) -> None:
        """Compile Objective-C specific regex patterns."""
        try:
            self._third_party_patterns = [
                # CocoaPods patterns
                re.compile(r'^[A-Z][a-zA-Z0-9]*$'),  # CamelCase frameworks
                re.compile(r'^FB[A-Z][a-zA-Z0-9]*'),  # Facebook frameworks
                re.compile(r'^AF[A-Z][a-zA-Z0-9]*'),  # AFNetworking family
                re.compile(r'^SD[A-Z][a-zA-Z0-9]*'),  # SDWebImage family
                re.compile(r'^MB[A-Z][a-zA-Z0-9]*'),  # MBProgressHUD family
                re.compile(r'^Google[A-Z][a-zA-Z0-9]*'),  # Google frameworks
                re.compile(r'^Firebase[A-Z][a-zA-Z0-9]*'),  # Firebase frameworks
            ]

            self._local_patterns = [
                # Private frameworks
                re.compile(r'Private'),
                re.compile(r'Internal'),
                # Local project patterns
                re.compile(r'^[a-z]'),  # lowercase frameworks are usually local
                re.compile(r'\.framework'),
                re.compile(r'/'),  # Path-based imports
            ]
        except Exception as e:
            logger.warning(f"Error compiling Objective-C patterns: {e}")

    def _classify_import_impl(self, import_path: str, context: Dict[str, any] = None) -> str:
        """Objective-C specific import classification."""
        # Check for common third-party frameworks
        common_third_party = {
            'AFNetworking', 'Alamofire', 'SDWebImage', 'MBProgressHUD',
            'JSONModel', 'RestKit', 'Firebase', 'ReactiveCocoa',
            'Masonry', 'SnapKit', 'Realm', 'FMDB', 'SQLite',
            'GoogleAnalytics', 'Fabric', 'Crashlytics', 'TestFlight',
            'Facebook', 'Twitter', 'Instagram', 'FBSDKCoreKit',
            'GoogleMaps', 'GooglePlaces', 'GoogleSignIn',
            'FirebaseCore', 'FirebaseAuth', 'FirebaseFirestore',
            'FirebaseDatabase', 'FirebaseStorage', 'FirebaseAnalytics',
            'Lottie', 'Charts', 'YYKit', 'Pop', 'IGListKit',
            'ComponentKit', 'Texture', 'AsyncDisplayKit'
        }

        base_framework = self.get_package_name_from_import(import_path)
        if base_framework in common_third_party:
            return 'third_party'

        # Check for CocoaPods/Carthage patterns
        if any(indicator in import_path for indicator in ['Pods/', 'Carthage/', 'Build/Products']):
            return 'third_party'

        # Check context for dependency management info
        if context:
            # Check Podfile dependencies
            pods = context.get('cocoapods_dependencies', set())
            if base_framework in pods:
                return 'third_party'

            # Check Cartfile dependencies
            carthage_deps = context.get('carthage_dependencies', set())
            if base_framework in carthage_deps:
                return 'third_party'

            # Check SPM dependencies
            spm_deps = context.get('spm_dependencies', set())
            if base_framework in spm_deps:
                return 'third_party'

        # Private or internal frameworks are local
        if 'Private' in import_path or 'Internal' in import_path:
            return 'local'

        # Default to standard_library for unknown Apple frameworks
        # (Objective-C ecosystem has many system frameworks)
        return 'standard_library'

    def normalize_import_path(self, raw_path: str) -> str:
        """Normalize Objective-C import path."""
        normalized = raw_path.strip()

        # Remove .framework suffix
        if normalized.endswith('.framework'):
            normalized = normalized[:-10]

        # Remove file extensions
        for ext in ['.h', '.m', '.mm']:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break

        # Extract framework name from paths
        if '/' in normalized:
            # Extract the last component (framework name)
            normalized = normalized.split('/')[-1]

        return normalized

    def get_package_manager_files(self) -> Set[str]:
        """Return Objective-C package manager files."""
        return {
            'Podfile',
            'Podfile.lock',
            'Cartfile',
            'Cartfile.resolved',
            'Package.swift',
            'Package.resolved',
            'project.pbxproj'  # Xcode project file
        }

    def extract_dependencies_from_file(self, file_path: str, file_content: str) -> List[str]:
        """Extract dependencies from Objective-C package manager files."""
        dependencies = []

        try:
            if 'Podfile' in file_path and not file_path.endswith('.lock'):
                dependencies = self._parse_podfile(file_content)
            elif file_path.endswith('Podfile.lock'):
                dependencies = self._parse_podfile_lock(file_content)
            elif 'Cartfile' in file_path:
                dependencies = self._parse_cartfile(file_content)
            elif file_path.endswith('Package.swift'):
                dependencies = self._parse_package_swift(file_content)
            elif file_path.endswith('project.pbxproj'):
                dependencies = self._parse_pbxproj(file_content)
        except Exception as e:
            logger.debug(f"Error parsing Objective-C dependency file {file_path}: {e}")

        return dependencies

    def _parse_podfile(self, content: str) -> List[str]:
        """Parse Podfile for CocoaPods dependencies."""
        dependencies = []
        try:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('pod '):
                    # Extract pod name
                    match = re.search(r"pod\s+['\"]([^'\"]+)['\"]", line)
                    if match:
                        pod_name = match.group(1)
                        dependencies.append(pod_name)
        except Exception as e:
            logger.debug(f"Error parsing Podfile: {e}")

        return dependencies

    def _parse_podfile_lock(self, content: str) -> List[str]:
        """Parse Podfile.lock for installed pods."""
        dependencies = []
        try:
            in_pods_section = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('PODS:'):
                    in_pods_section = True
                    continue
                elif in_pods_section and line.startswith('DEPENDENCIES:'):
                    break
                elif in_pods_section and line.startswith('- '):
                    # Extract pod name
                    pod_spec = line[2:].strip()
                    if '(' in pod_spec:
                        pod_name = pod_spec.split('(')[0].strip()
                    else:
                        pod_name = pod_spec.split(' ')[0].strip()
                    if pod_name:
                        dependencies.append(pod_name)
        except Exception as e:
            logger.debug(f"Error parsing Podfile.lock: {e}")

        return dependencies

    def _parse_cartfile(self, content: str) -> List[str]:
        """Parse Cartfile for Carthage dependencies."""
        dependencies = []
        try:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract dependency name from Carthage format
                    parts = line.split()
                    if len(parts) >= 2:
                        repo = parts[1]
                        if '/' in repo:
                            # Extract framework name from GitHub repo
                            framework_name = repo.split('/')[-1]
                            if framework_name:
                                dependencies.append(framework_name)
        except Exception as e:
            logger.debug(f"Error parsing Cartfile: {e}")

        return dependencies

    def _parse_package_swift(self, content: str) -> List[str]:
        """Parse Package.swift for Swift Package Manager dependencies."""
        dependencies = []
        try:
            # Look for .package declarations
            for line in content.splitlines():
                line = line.strip()
                if '.package(' in line:
                    # Extract package name or URL
                    match = re.search(r'url:\s*["\']([^"\']+)["\']', line)
                    if match:
                        url = match.group(1)
                        if '/' in url:
                            package_name = url.split('/')[-1]
                            if package_name.endswith('.git'):
                                package_name = package_name[:-4]
                            dependencies.append(package_name)
        except Exception as e:
            logger.debug(f"Error parsing Package.swift: {e}")

        return dependencies

    def _parse_pbxproj(self, content: str) -> List[str]:
        """Parse Xcode project file for framework references."""
        dependencies = []
        try:
            # Look for framework references in pbxproj
            for line in content.splitlines():
                if '.framework' in line:
                    # Extract framework names
                    matches = re.findall(r'([A-Za-z0-9_]+)\.framework', line)
                    for framework in matches:
                        if framework not in dependencies:
                            dependencies.append(framework)
        except Exception as e:
            logger.debug(f"Error parsing project.pbxproj: {e}")

        return dependencies

    def get_package_name_from_import(self, import_path: str) -> str:
        """Extract framework name from Objective-C import path."""
        # Remove common prefixes/suffixes
        normalized = import_path

        if normalized.endswith('.framework'):
            normalized = normalized[:-10]

        # Extract framework name from paths
        if '/' in normalized:
            normalized = normalized.split('/')[-1]

        # Remove file extensions
        for ext in ['.h', '.m', '.mm']:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break

        return normalized
