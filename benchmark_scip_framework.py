"""SCIP Framework Performance Benchmark Suite - Comprehensive performance testing and analysis."""

import os
import time
import tempfile
import statistics
import gc
import psutil
import threading
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.code_index_mcp.scip.framework import (
    SCIPFrameworkAPI, SCIPConfig, create_scip_framework,
    PythonSCIPIndexFactory, JavaScriptSCIPIndexFactory, JavaSCIPIndexFactory,
    SCIPCacheManager, StreamingIndexer
)


@dataclass
class BenchmarkResult:
    """Benchmark result data structure."""
    test_name: str
    file_count: int
    total_time: float
    memory_usage_mb: float
    symbols_generated: int
    occurrences_generated: int
    cache_hit_rate: float
    throughput_files_per_sec: float
    throughput_symbols_per_sec: float
    error_count: int
    additional_metrics: Dict[str, Any]


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float


class PerformanceMonitor:
    """Real-time performance monitoring during benchmarks."""
    
    def __init__(self):
        self.monitoring = False
        self.metrics_history: List[SystemMetrics] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.process = psutil.Process()
    
    def start_monitoring(self, interval: float = 0.5):
        """Start performance monitoring."""
        self.monitoring = True
        self.metrics_history.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> List[SystemMetrics]:
        """Stop monitoring and return collected metrics."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        return self.metrics_history.copy()
    
    def _monitor_loop(self, interval: float):
        """Monitor system metrics in a loop."""
        while self.monitoring:
            try:
                # Get current metrics
                memory_info = self.process.memory_info()
                
                metrics = SystemMetrics(
                    cpu_percent=self.process.cpu_percent(),
                    memory_percent=self.process.memory_percent(),
                    memory_available_mb=memory_info.rss / 1024 / 1024,
                    disk_io_read_mb=0.0,  # Simplified for demo
                    disk_io_write_mb=0.0
                )
                
                self.metrics_history.append(metrics)
                time.sleep(interval)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                break


class SCIPFrameworkBenchmark:
    """Comprehensive benchmark suite for SCIP framework."""
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.monitor = PerformanceMonitor()
        
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        print("=== SCIP Framework Performance Benchmark Suite ===")
        print(f"System: {psutil.cpu_count()} CPUs, {psutil.virtual_memory().total // 1024**3} GB RAM")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test projects of various sizes
            small_project = self.create_test_project(temp_dir, "small", 50)
            medium_project = self.create_test_project(temp_dir, "medium", 200)
            large_project = self.create_test_project(temp_dir, "large", 1000)
            
            # Run benchmarks
            benchmark_suite = [
                ("Small Project (50 files)", small_project, {'max_workers': 2, 'batch_size': 10}),
                ("Medium Project (200 files)", medium_project, {'max_workers': 4, 'batch_size': 50}),
                ("Large Project (1000 files)", large_project, {'max_workers': 8, 'batch_size': 100}),
            ]
            
            for test_name, project_path, config_overrides in benchmark_suite:
                print(f"\n🏃 Running: {test_name}")
                
                # Basic index generation benchmark
                result = self.benchmark_index_generation(test_name, project_path, config_overrides)
                self.results.append(result)
                
                # Caching performance benchmark
                cache_result = self.benchmark_caching_performance(f"{test_name} - Caching", project_path, config_overrides)
                self.results.append(cache_result)
                
                # Streaming performance benchmark
                streaming_result = self.benchmark_streaming_performance(f"{test_name} - Streaming", project_path, config_overrides)
                self.results.append(streaming_result)
            
            # Multi-language benchmark
            multi_lang_project = self.create_multi_language_project(temp_dir)
            multi_result = self.benchmark_multi_language(multi_lang_project)
            self.results.append(multi_result)
            
            # Memory stress test
            memory_result = self.benchmark_memory_usage(large_project)
            self.results.append(memory_result)
            
            # Concurrent processing benchmark
            concurrent_result = self.benchmark_concurrent_processing(medium_project)
            self.results.append(concurrent_result)
        
        # Generate comprehensive report
        return self.generate_benchmark_report()
    
    def create_test_project(self, base_dir: str, project_name: str, file_count: int) -> str:
        """Create test project with specified number of files."""
        project_dir = os.path.join(base_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        # Generate Python files with varying complexity
        for i in range(file_count):
            file_path = os.path.join(project_dir, f"module_{i:04d}.py")
            content = self.generate_python_file_content(i, file_count)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return project_dir
    
    def create_multi_language_project(self, base_dir: str) -> str:
        """Create project with multiple programming languages."""
        project_dir = os.path.join(base_dir, "multi_language")
        os.makedirs(project_dir, exist_ok=True)
        
        # Python files
        for i in range(30):
            file_path = os.path.join(project_dir, f"python_module_{i}.py")
            with open(file_path, 'w') as f:
                f.write(self.generate_python_file_content(i, 30))
        
        # JavaScript files
        for i in range(20):
            file_path = os.path.join(project_dir, f"js_module_{i}.js")
            with open(file_path, 'w') as f:
                f.write(self.generate_javascript_file_content(i))
        
        # Java files
        for i in range(15):
            file_path = os.path.join(project_dir, f"JavaClass_{i}.java")
            with open(file_path, 'w') as f:
                f.write(self.generate_java_file_content(i))
        
        return project_dir
    
    def generate_python_file_content(self, file_index: int, total_files: int) -> str:
        """Generate Python file content with realistic complexity."""
        imports_count = min(5, file_index % 8 + 1)
        classes_count = file_index % 3 + 1
        functions_count = file_index % 5 + 2
        
        content = f'"""Module {file_index} - Generated for performance testing."""\n\n'
        
        # Add imports
        for i in range(imports_count):
            import_target = f"module_{(file_index + i) % total_files:04d}"
            content += f"from {import_target} import Class{i}, function_{i}\n"
        
        content += "\nimport os\nimport sys\nfrom typing import List, Dict, Optional\n\n"
        
        # Add classes
        for class_i in range(classes_count):
            content += f'''
class Class{file_index}_{class_i}:
    """Test class {class_i} in module {file_index}."""
    
    def __init__(self, value: int = 0):
        self.value = value
        self.data: Dict[str, int] = {{}}
        self.items: List[str] = []
    
    def process_data(self, input_data: List[int]) -> Dict[str, int]:
        """Process input data and return results."""
        result = {{}}
        for i, item in enumerate(input_data):
            key = f"item_{{i}}"
            result[key] = item * self.value
        return result
    
    def calculate_total(self, multiplier: float = 1.0) -> float:
        """Calculate total value."""
        return sum(self.data.values()) * multiplier
    
    def add_item(self, item: str) -> None:
        """Add item to collection."""
        if item not in self.items:
            self.items.append(item)
    
    @property
    def item_count(self) -> int:
        """Get number of items."""
        return len(self.items)
'''
        
        # Add functions
        for func_i in range(functions_count):
            content += f'''
def function_{file_index}_{func_i}(param1: int, param2: str = "default") -> Tuple[int, str]:
    """Function {func_i} in module {file_index}."""
    processed_value = param1 * {func_i + 1}
    processed_string = f"{{param2}}_{{processed_value}}"
    
    # Some processing logic
    if processed_value > 100:
        processed_value = processed_value // 2
    
    return processed_value, processed_string

def helper_function_{file_index}_{func_i}(data: List[Any]) -> Optional[Any]:
    """Helper function for function_{func_i}."""
    if not data:
        return None
    
    return data[0] if len(data) == 1 else data
'''
        
        # Add module-level variables
        content += f'''
# Module-level variables
MODULE_ID = {file_index}
MODULE_NAME = "module_{file_index:04d}"
DEFAULT_CONFIG = {{
    "enabled": True,
    "max_items": {file_index * 10 + 100},
    "timeout": {file_index * 2 + 30}
}}
'''
        
        return content
    
    def generate_javascript_file_content(self, file_index: int) -> str:
        """Generate JavaScript file content."""
        return f'''
// JavaScript module {file_index} for performance testing
const express = require('express');
const {{ EventEmitter }} = require('events');

class Service{file_index} extends EventEmitter {{
    constructor(config = {{}}) {{
        super();
        this.config = config;
        this.data = new Map();
        this.active = false;
    }}
    
    async initialize() {{
        this.active = true;
        this.emit('initialized', {{ serviceId: {file_index} }});
    }}
    
    processData(input) {{
        const result = [];
        for (const item of input) {{
            result.push({{
                id: item.id,
                value: item.value * {file_index},
                timestamp: Date.now()
            }});
        }}
        return result;
    }}
    
    async asyncOperation(delay = 100) {{
        return new Promise(resolve => {{
            setTimeout(() => {{
                resolve({{ result: 'completed', serviceId: {file_index} }});
            }}, delay);
        }});
    }}
}}

function helper{file_index}(data) {{
    return data.map(item => ({{
        ...item,
        processed: true,
        serviceId: {file_index}
    }}));
}}

const config{file_index} = {{
    serviceId: {file_index},
    enabled: true,
    maxConnections: {file_index * 10 + 50}
}};

module.exports = {{
    Service{file_index},
    helper{file_index},
    config{file_index}
}};
'''
    
    def generate_java_file_content(self, file_index: int) -> str:
        """Generate Java file content."""
        return f'''
package com.benchmark.test;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.time.LocalDateTime;

/**
 * Test class {file_index} for performance benchmarking.
 * Demonstrates various Java language features.
 */
public class JavaClass_{file_index} {{
    private final int classId;
    private final Map<String, Object> data;
    private final List<String> items;
    private boolean active;
    
    /**
     * Constructor for JavaClass_{file_index}.
     * 
     * @param classId Unique identifier for this class
     */
    public JavaClass_{file_index}(int classId) {{
        this.classId = classId;
        this.data = new ConcurrentHashMap<>();
        this.items = new ArrayList<>();
        this.active = false;
    }}
    
    /**
     * Initialize the class with default values.
     */
    public void initialize() {{
        this.active = true;
        this.data.put("initialized", LocalDateTime.now());
        this.data.put("classId", this.classId);
    }}
    
    /**
     * Process a list of integers and return results.
     * 
     * @param input List of integers to process
     * @return Map of processed results
     */
    public Map<String, Integer> processNumbers(List<Integer> input) {{
        Map<String, Integer> results = new HashMap<>();
        
        for (int i = 0; i < input.size(); i++) {{
            String key = "result_" + i;
            Integer value = input.get(i) * {file_index} + i;
            results.put(key, value);
        }}
        
        return results;
    }}
    
    /**
     * Add item to the collection.
     * 
     * @param item Item to add
     * @return true if item was added, false if it already exists
     */
    public boolean addItem(String item) {{
        if (item == null || item.trim().isEmpty()) {{
            return false;
        }}
        
        if (!items.contains(item)) {{
            items.add(item);
            return true;
        }}
        
        return false;
    }}
    
    /**
     * Get total count of items.
     * 
     * @return Number of items in collection
     */
    public int getItemCount() {{
        return items.size();
    }}
    
    /**
     * Check if class is active.
     * 
     * @return true if active, false otherwise
     */
    public boolean isActive() {{
        return active;
    }}
    
    /**
     * Set active status.
     * 
     * @param active New active status
     */
    public void setActive(boolean active) {{
        this.active = active;
        if (active) {{
            data.put("lastActivated", LocalDateTime.now());
        }}
    }}
    
    @Override
    public String toString() {{
        return String.format("JavaClass_%d{{classId=%d, active=%s, items=%d}}", 
                           {file_index}, classId, active, items.size());
    }}
    
    @Override
    public boolean equals(Object obj) {{
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        JavaClass_{file_index} other = (JavaClass_{file_index}) obj;
        return classId == other.classId;
    }}
    
    @Override
    public int hashCode() {{
        return Objects.hash(classId);
    }}
}}
'''
    
    def benchmark_index_generation(self, test_name: str, project_path: str, config_overrides: Dict) -> BenchmarkResult:
        """Benchmark basic index generation performance."""
        print(f"  📊 Index generation benchmark...")
        
        # Configure framework
        config = SCIPConfig(
            project_root=project_path,
            cache_enabled=False,  # Disable cache for pure generation benchmark
            validate_compliance=True,
            **config_overrides
        )
        
        framework = SCIPFrameworkAPI(config)
        
        # Count files
        file_count = len(list(Path(project_path).rglob("*.py")))
        
        # Start monitoring
        self.monitor.start_monitoring()
        
        # Run benchmark
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            index = framework.create_complete_index()
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Stop monitoring
            metrics_history = self.monitor.stop_monitoring()
            
            # Calculate metrics
            total_time = end_time - start_time
            memory_usage = end_memory - start_memory
            
            symbols_count = sum(len(doc.symbols) for doc in index.documents)
            occurrences_count = sum(len(doc.occurrences) for doc in index.occurrences)
            
            throughput_files = file_count / total_time if total_time > 0 else 0
            throughput_symbols = symbols_count / total_time if total_time > 0 else 0
            
            # Additional metrics
            avg_cpu = statistics.mean([m.cpu_percent for m in metrics_history]) if metrics_history else 0
            peak_memory = max([m.memory_available_mb for m in metrics_history]) if metrics_history else end_memory
            
            result = BenchmarkResult(
                test_name=test_name,
                file_count=file_count,
                total_time=total_time,
                memory_usage_mb=memory_usage,
                symbols_generated=symbols_count,
                occurrences_generated=occurrences_count,
                cache_hit_rate=0.0,  # No cache in this test
                throughput_files_per_sec=throughput_files,
                throughput_symbols_per_sec=throughput_symbols,
                error_count=0,
                additional_metrics={
                    'avg_cpu_percent': avg_cpu,
                    'peak_memory_mb': peak_memory,
                    'documents_generated': len(index.documents),
                    'external_symbols': len(index.external_symbols)
                }
            )
            
            print(f"    ✓ {file_count} files, {symbols_count} symbols in {total_time:.2f}s")
            print(f"    ✓ {throughput_files:.1f} files/sec, {throughput_symbols:.1f} symbols/sec")
            
            return result
            
        except Exception as e:
            self.monitor.stop_monitoring()
            print(f"    ❌ Benchmark failed: {e}")
            
            return BenchmarkResult(
                test_name=f"{test_name} (FAILED)",
                file_count=file_count,
                total_time=0,
                memory_usage_mb=0,
                symbols_generated=0,
                occurrences_generated=0,
                cache_hit_rate=0.0,
                throughput_files_per_sec=0,
                throughput_symbols_per_sec=0,
                error_count=1,
                additional_metrics={'error': str(e)}
            )
    
    def benchmark_caching_performance(self, test_name: str, project_path: str, config_overrides: Dict) -> BenchmarkResult:
        """Benchmark caching system performance."""
        print(f"  🗂️  Caching performance benchmark...")
        
        config = SCIPConfig(
            project_root=project_path,
            cache_enabled=True,
            **config_overrides
        )
        
        framework = SCIPFrameworkAPI(config)
        file_count = len(list(Path(project_path).rglob("*.py")))
        
        # First run to populate cache
        start_time = time.time()
        index1 = framework.create_complete_index()
        first_run_time = time.time() - start_time
        
        # Second run with cache
        start_time = time.time()
        index2 = framework.create_complete_index()
        second_run_time = time.time() - start_time
        
        # Get cache statistics
        cache_stats = framework.get_cache_statistics()
        hit_rate = float(cache_stats.get('hit_rate', '0%').rstrip('%')) / 100.0
        
        symbols_count = sum(len(doc.symbols) for doc in index2.documents)
        
        result = BenchmarkResult(
            test_name=test_name,
            file_count=file_count,
            total_time=second_run_time,
            memory_usage_mb=0,  # Not measured in this test
            symbols_generated=symbols_count,
            occurrences_generated=0,
            cache_hit_rate=hit_rate,
            throughput_files_per_sec=file_count / second_run_time if second_run_time > 0 else 0,
            throughput_symbols_per_sec=symbols_count / second_run_time if second_run_time > 0 else 0,
            error_count=0,
            additional_metrics={
                'first_run_time': first_run_time,
                'second_run_time': second_run_time,
                'cache_speedup': first_run_time / second_run_time if second_run_time > 0 else 0,
                'cache_entries': cache_stats.get('memory_entries', 0)
            }
        )
        
        speedup = first_run_time / second_run_time if second_run_time > 0 else 0
        print(f"    ✓ Cache hit rate: {hit_rate:.1%}, speedup: {speedup:.1f}x")
        
        return result
    
    def benchmark_streaming_performance(self, test_name: str, project_path: str, config_overrides: Dict) -> BenchmarkResult:
        """Benchmark streaming indexer performance."""
        print(f"  🌊 Streaming performance benchmark...")
        
        config = SCIPConfig(
            project_root=project_path,
            cache_enabled=True,
            **config_overrides
        )
        
        framework = SCIPFrameworkAPI(config)
        python_files = list(Path(project_path).rglob("*.py"))
        file_paths = [str(f) for f in python_files]
        
        # Create streaming indexer
        python_factory = PythonSCIPIndexFactory(project_path)
        cache_manager = SCIPCacheManager()
        streaming_indexer = StreamingIndexer(
            factory=python_factory,
            cache_manager=cache_manager,
            max_workers=config_overrides.get('max_workers', 4),
            chunk_size=config_overrides.get('batch_size', 50) // 2
        )
        
        # Track progress
        progress_updates = []
        def track_progress(progress):
            progress_updates.append({
                'percentage': progress.progress_percentage,
                'elapsed': progress.elapsed_time
            })
        
        streaming_indexer.add_progress_callback(track_progress)
        
        # Run streaming benchmark
        start_time = time.time()
        
        documents = []
        for doc in streaming_indexer.index_files_streaming(file_paths):
            documents.append(doc)
        
        total_time = time.time() - start_time
        
        symbols_count = sum(len(doc.symbols) for doc in documents)
        occurrences_count = sum(len(doc.occurrences) for doc in documents)
        
        result = BenchmarkResult(
            test_name=test_name,
            file_count=len(file_paths),
            total_time=total_time,
            memory_usage_mb=0,
            symbols_generated=symbols_count,
            occurrences_generated=occurrences_count,
            cache_hit_rate=0.0,
            throughput_files_per_sec=len(file_paths) / total_time if total_time > 0 else 0,
            throughput_symbols_per_sec=symbols_count / total_time if total_time > 0 else 0,
            error_count=0,
            additional_metrics={
                'progress_updates': len(progress_updates),
                'avg_chunk_time': total_time / max(1, len(progress_updates)),
                'documents_streamed': len(documents)
            }
        )
        
        print(f"    ✓ Streamed {len(documents)} documents in {total_time:.2f}s")
        
        return result
    
    def benchmark_multi_language(self, project_path: str) -> BenchmarkResult:
        """Benchmark multi-language processing."""
        print(f"  🌐 Multi-language performance benchmark...")
        
        config = SCIPConfig(
            project_root=project_path,
            max_workers=6,
            supported_languages={'python', 'javascript', 'java'}
        )
        
        framework = SCIPFrameworkAPI(config)
        
        # Count files by language
        python_files = len(list(Path(project_path).rglob("*.py")))
        js_files = len(list(Path(project_path).rglob("*.js")))
        java_files = len(list(Path(project_path).rglob("*.java")))
        total_files = python_files + js_files + java_files
        
        # Run benchmark
        start_time = time.time()
        index = framework.create_complete_index()
        total_time = time.time() - start_time
        
        symbols_count = sum(len(doc.symbols) for doc in index.documents)
        
        result = BenchmarkResult(
            test_name="Multi-Language Processing",
            file_count=total_files,
            total_time=total_time,
            memory_usage_mb=0,
            symbols_generated=symbols_count,
            occurrences_generated=0,
            cache_hit_rate=0.0,
            throughput_files_per_sec=total_files / total_time if total_time > 0 else 0,
            throughput_symbols_per_sec=symbols_count / total_time if total_time > 0 else 0,
            error_count=0,
            additional_metrics={
                'python_files': python_files,
                'javascript_files': js_files,
                'java_files': java_files,
                'languages_processed': 3,
                'documents_generated': len(index.documents)
            }
        )
        
        print(f"    ✓ {total_files} files ({python_files} Python, {js_files} JS, {java_files} Java)")
        print(f"    ✓ {symbols_count} symbols in {total_time:.2f}s")
        
        return result
    
    def benchmark_memory_usage(self, project_path: str) -> BenchmarkResult:
        """Benchmark memory usage under load."""
        print(f"  🧠 Memory usage benchmark...")
        
        # Configure for memory stress testing
        config = SCIPConfig(
            project_root=project_path,
            max_workers=1,  # Single worker to control memory usage
            batch_size=10,  # Small batches
            cache_enabled=True
        )
        
        framework = SCIPFrameworkAPI(config)
        file_count = len(list(Path(project_path).rglob("*.py")))
        
        # Monitor memory throughout the process
        self.monitor.start_monitoring(interval=0.1)  # High frequency monitoring
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        start_time = time.time()
        
        # Process with memory monitoring
        index = framework.create_complete_index()
        
        total_time = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024
        
        # Stop monitoring and analyze
        metrics_history = self.monitor.stop_monitoring()
        
        if metrics_history:
            peak_memory = max(m.memory_available_mb for m in metrics_history)
            avg_memory = statistics.mean(m.memory_available_mb for m in metrics_history)
        else:
            peak_memory = final_memory
            avg_memory = final_memory
        
        memory_growth = final_memory - initial_memory
        symbols_count = sum(len(doc.symbols) for doc in index.documents)
        
        result = BenchmarkResult(
            test_name="Memory Usage Analysis",
            file_count=file_count,
            total_time=total_time,
            memory_usage_mb=memory_growth,
            symbols_generated=symbols_count,
            occurrences_generated=0,
            cache_hit_rate=0.0,
            throughput_files_per_sec=file_count / total_time if total_time > 0 else 0,
            throughput_symbols_per_sec=symbols_count / total_time if total_time > 0 else 0,
            error_count=0,
            additional_metrics={
                'initial_memory_mb': initial_memory,
                'final_memory_mb': final_memory,
                'peak_memory_mb': peak_memory,
                'avg_memory_mb': avg_memory,
                'memory_efficiency_mb_per_symbol': memory_growth / symbols_count if symbols_count > 0 else 0,
                'monitoring_samples': len(metrics_history)
            }
        )
        
        print(f"    ✓ Memory growth: {memory_growth:.1f} MB (peak: {peak_memory:.1f} MB)")
        print(f"    ✓ {memory_growth/symbols_count:.3f} MB per symbol")
        
        return result
    
    def benchmark_concurrent_processing(self, project_path: str) -> BenchmarkResult:
        """Benchmark concurrent processing capabilities."""
        print(f"  ⚡ Concurrent processing benchmark...")
        
        python_files = list(Path(project_path).rglob("*.py"))
        file_paths = [str(f) for f in python_files]
        
        # Test different worker counts
        worker_counts = [1, 2, 4, 8]
        results = {}
        
        for workers in worker_counts:
            config = SCIPConfig(
                project_root=project_path,
                max_workers=workers,
                batch_size=50
            )
            
            framework = SCIPFrameworkAPI(config)
            
            start_time = time.time()
            index = framework.create_complete_index()
            elapsed_time = time.time() - start_time
            
            results[workers] = {
                'time': elapsed_time,
                'symbols': sum(len(doc.symbols) for doc in index.documents)
            }
        
        # Find optimal worker count
        best_workers = min(results.keys(), key=lambda w: results[w]['time'])
        best_time = results[best_workers]['time']
        sequential_time = results[1]['time']
        
        speedup = sequential_time / best_time if best_time > 0 else 0
        efficiency = speedup / best_workers if best_workers > 0 else 0
        
        result = BenchmarkResult(
            test_name="Concurrent Processing Analysis",
            file_count=len(file_paths),
            total_time=best_time,
            memory_usage_mb=0,
            symbols_generated=results[best_workers]['symbols'],
            occurrences_generated=0,
            cache_hit_rate=0.0,
            throughput_files_per_sec=len(file_paths) / best_time if best_time > 0 else 0,
            throughput_symbols_per_sec=results[best_workers]['symbols'] / best_time if best_time > 0 else 0,
            error_count=0,
            additional_metrics={
                'optimal_workers': best_workers,
                'speedup': speedup,
                'efficiency': efficiency,
                'worker_results': results,
                'parallel_efficiency_percent': efficiency * 100
            }
        )
        
        print(f"    ✓ Optimal workers: {best_workers}, speedup: {speedup:.1f}x")
        print(f"    ✓ Parallel efficiency: {efficiency:.1%}")
        
        return result
    
    def generate_benchmark_report(self) -> Dict[str, Any]:
        """Generate comprehensive benchmark report."""
        if not self.results:
            return {"error": "No benchmark results available"}
        
        # Calculate aggregate statistics
        total_files = sum(r.file_count for r in self.results)
        total_symbols = sum(r.symbols_generated for r in self.results)
        total_time = sum(r.total_time for r in self.results)
        
        # Performance metrics
        avg_throughput_files = statistics.mean([r.throughput_files_per_sec for r in self.results if r.throughput_files_per_sec > 0])
        avg_throughput_symbols = statistics.mean([r.throughput_symbols_per_sec for r in self.results if r.throughput_symbols_per_sec > 0])
        
        # Memory analysis
        memory_results = [r for r in self.results if r.memory_usage_mb > 0]
        avg_memory_usage = statistics.mean([r.memory_usage_mb for r in memory_results]) if memory_results else 0
        
        # Cache performance
        cache_results = [r for r in self.results if r.cache_hit_rate > 0]
        avg_cache_hit_rate = statistics.mean([r.cache_hit_rate for r in cache_results]) if cache_results else 0
        
        # System information
        system_info = {
            'cpu_count': psutil.cpu_count(),
            'cpu_freq_mhz': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            'memory_total_gb': psutil.virtual_memory().total / 1024**3,
            'memory_available_gb': psutil.virtual_memory().available / 1024**3,
            'disk_usage_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
        }
        
        # Performance summary
        performance_summary = {
            'total_benchmarks': len(self.results),
            'total_files_processed': total_files,
            'total_symbols_generated': total_symbols,
            'total_processing_time': total_time,
            'average_throughput_files_per_sec': avg_throughput_files,
            'average_throughput_symbols_per_sec': avg_throughput_symbols,
            'average_memory_usage_mb': avg_memory_usage,
            'average_cache_hit_rate': avg_cache_hit_rate,
            'failed_benchmarks': len([r for r in self.results if r.error_count > 0])
        }
        
        # Detailed results
        detailed_results = []
        for result in self.results:
            detailed_results.append(asdict(result))
        
        # Performance recommendations
        recommendations = self.generate_performance_recommendations()
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'system_info': system_info,
            'performance_summary': performance_summary,
            'detailed_results': detailed_results,
            'recommendations': recommendations
        }
        
        # Print summary
        print("\n" + "="*60)
        print("📊 BENCHMARK RESULTS SUMMARY")
        print("="*60)
        print(f"Total benchmarks: {len(self.results)}")
        print(f"Files processed: {total_files:,}")
        print(f"Symbols generated: {total_symbols:,}")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average throughput: {avg_throughput_files:.1f} files/sec, {avg_throughput_symbols:.1f} symbols/sec")
        print(f"Average memory usage: {avg_memory_usage:.1f} MB")
        if avg_cache_hit_rate > 0:
            print(f"Average cache hit rate: {avg_cache_hit_rate:.1%}")
        print()
        
        # Print individual results
        for result in self.results:
            status = "✓" if result.error_count == 0 else "❌"
            print(f"{status} {result.test_name}")
            print(f"   {result.file_count} files → {result.symbols_generated} symbols in {result.total_time:.2f}s")
            print(f"   {result.throughput_files_per_sec:.1f} files/sec, {result.throughput_symbols_per_sec:.1f} symbols/sec")
            if result.cache_hit_rate > 0:
                print(f"   Cache hit rate: {result.cache_hit_rate:.1%}")
            print()
        
        return report
    
    def generate_performance_recommendations(self) -> List[str]:
        """Generate performance recommendations based on benchmark results."""
        recommendations = []
        
        # Analyze results for recommendations
        memory_results = [r for r in self.results if r.memory_usage_mb > 0]
        if memory_results:
            avg_memory = statistics.mean([r.memory_usage_mb for r in memory_results])
            if avg_memory > 500:  # More than 500 MB
                recommendations.append("Consider reducing batch_size or max_workers to control memory usage")
        
        # Cache performance
        cache_results = [r for r in self.results if r.cache_hit_rate > 0]
        if cache_results:
            avg_cache_rate = statistics.mean([r.cache_hit_rate for r in cache_results])
            if avg_cache_rate < 0.7:  # Less than 70% hit rate
                recommendations.append("Cache performance is suboptimal. Consider increasing cache size or optimizing file change detection")
        
        # Throughput analysis
        throughput_results = [r.throughput_files_per_sec for r in self.results if r.throughput_files_per_sec > 0]
        if throughput_results:
            avg_throughput = statistics.mean(throughput_results)
            if avg_throughput < 10:  # Less than 10 files per second
                recommendations.append("Consider increasing max_workers or batch_size to improve throughput")
        
        # Concurrent processing
        concurrent_results = [r for r in self.results if 'speedup' in r.additional_metrics]
        if concurrent_results:
            for result in concurrent_results:
                efficiency = result.additional_metrics.get('efficiency', 0)
                if efficiency < 0.5:  # Less than 50% efficiency
                    recommendations.append("Parallel processing efficiency is low. Consider reducing worker count or optimizing workload distribution")
        
        # General recommendations
        recommendations.extend([
            "Enable caching for repeated operations to improve performance",
            "Use SSD storage for cache directory to reduce I/O latency",
            "Monitor memory usage during large project processing",
            "Consider streaming processing for very large codebases",
            "Validate SCIP compliance only when necessary for better performance"
        ])
        
        return recommendations


def run_benchmark_suite():
    """Main function to run the complete benchmark suite."""
    benchmark = SCIPFrameworkBenchmark()
    
    try:
        report = benchmark.run_all_benchmarks()
        
        # Save report to file
        import json
        report_path = "scip_framework_benchmark_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Detailed benchmark report saved to: {report_path}")
        
        # Print recommendations
        print("\n🎯 PERFORMANCE RECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
        
        return report
        
    except Exception as e:
        print(f"❌ Benchmark suite failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    run_benchmark_suite()