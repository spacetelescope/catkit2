---
title: 'CATKit2: A High-Performance Framework for Laboratory Instrument Control'
tags:
  - Python
  - C++
  - hardware control
  - laboratory automation
  - adaptive optics
  - instrumentation
  - real-time systems
  - high-contrast imaging
authors:
  - name: Emiel H. Por
    orcid: 0000-0002-3961-083X
    affiliation: 1
  - name: Iva Laginja
    orcid: 0000-0003-1783-5023
    affiliation: 2
  - name: Rémi Soummer
    orcid: 0000-0003-2753-2819
    affiliation: 3
  - name: Sarah Steiger
    orcid: 0000-0002-4787-3285
    affiliation: 3
  - name: Raphaël Pourcelot
    orcid: 0000-0002-9758-051X
    affiliation: 4
  - name: Alexis Lau
    orcid: 0000-0003-0742-6277
    affiliation: 5
  - name: Lane Meier
    orcid: 0000-0003-3482-8589
    affiliation: 6
  - name: Christopher Moriarty
    orcid: 0000-0002-1757-7573
    affiliation: 7
  - name: Jules Fowler
    orcid: 0000-0002-0726-9323
    affiliation: 1
  - name: Marshall Perrin 
    orcid: 0000-0002-3191-8151
    affiliation: 3
  - name: Arnaud Sevin
    orcid: 0009-0005-4176-7632
    affiliation: 8
  - name: Augustin Demagny
    affiliation: 8
  - name: Leo Egger
    affiliation: 8
  - name: Johan Mazoyer
    orcid: 0000-0002-9133-3091
    affiliation: 8
  - name: Ananya Sahoo
    orcid: 0000-0003-2806-1254
    affiliation: 9
  - name: Erin Pougheon
    affiliation: 8
  
affiliations:
 - name: University of California, Santa Cruz, United States
   index: 1
   ror: 
 - name: Laboratoire Lagrange, Observatoire de la Cote d'Azur, Université Cote d'Azur, CNRS
   index: 2
   ror: 
 - name: Space Telescope Science Institute, United States
   index: 3
   ror: 
 - name: Max Planck Institute for Astrophysics,  Heidelberg, Germany
   index: 4
   ror: 
 - name: Laboratoire d'Astrophysique de Marseille, Marseille, France
   index: 5
   ror: 
 - name: Goddard Space Flight Center, Greenbelt, United States
   index: 6
   ror: 
 - name: self 
   index: 7
   ror: 
 - name: LIRA, Observatoire de Paris, France
   index: 8
   ror: 
 - name: Lowell Center for Space Science and Technology, United States 
   index: 9
   ror: 
     
date: 16 February 2026
bibliography: paper.bib
---

# Summary

CATKit2 (Control and Automation for Testbeds Kit 2) [@por_2024_11395554] is a high-performance software framework designed for controlling complex laboratory hardware systems. Developed primarily for adaptive optics and high-contrast imaging testbeds in astronomy, it provides a robust infrastructure for hardware synchronization, real-time data streaming, and distributed process management. The framework enables researchers to orchestrate multiple hardware devices—such as cameras, deformable mirrors, motorized stages, light sources, and sensors—into cohesive, synchronized experimental setups.

The software employs a service-oriented architecture where each hardware device or computational task runs as an independent service process. Services communicate through high-speed, low-latency data streams implemented via shared memory, enabling real-time data exchange between components with minimal overhead. A central testbed server manages service lifecycle, configuration distribution, and provides discovery mechanisms for clients. The framework supports both hardware operation and comprehensive simulation modes, allowing researchers to develop and test control algorithms without physical hardware.

CATKit2 is written in C++ for performance-critical operations with Python bindings for ease of use. It includes over 40 ready-to-use service implementations covering cameras (ZWO, FLIR, Hamamatsu, Allied Vision), deformable mirrors (Boston Micromachines), motion controllers (Newport, Thorlabs), spectrometers (Ocean Optics), and various other laboratory instruments. Each hardware service has a corresponding simulator, enabling full software-in-the-loop testing and algorithm development.

# Statement of need

Modern astronomical instrumentation relies increasingly on sophisticated laboratory testbeds to develop and validate technologies before deployment to observatories. These testbeds, such as the High-contrast Imager for Complex Apertures Testbed (HiCAT) [@hicat] at the Space Telescope Science Institute, require precise coordination of numerous hardware components operating at high speeds with strict timing requirements. Control frameworks must handle diverse hardware interfaces while maintaining microsecond-level synchronization and gigabyte-per-second data throughput.

Existing general-purpose laboratory automation tools often prioritize flexibility over performance, resulting in latency and jitter that are unacceptable for adaptive optics and wavefront sensing applications. Conversely, specialized control systems developed for specific instruments typically lack the modularity and extensibility needed for multi-purpose testbeds. There is a need for a framework that bridges this gap: providing both the performance required for real-time control loops and the flexibility to accommodate diverse hardware configurations.

CATKit2 addresses this need by combining a high-performance C++ core optimized for shared-memory data streaming with Python service implementations that enable rapid prototyping and integration with the scientific Python ecosystem. The framework's design prioritizes concurrent operation, allowing multiple processes to access streaming data simultaneously with minimal overhead. This architecture is particularly valuable for high-contrast imaging experiments where wavefront sensors must provide real-time feedback to deformable mirrors while data is simultaneously logged and visualized.

# State of the field

Several frameworks exist for laboratory hardware control, each with distinct design goals that influence their suitability for high-performance testbed applications. At the large-scale facility level, the Experimental Physics and Industrial Control System (EPICS) [@epics] provides robust distributed control through channel access protocols, excelling at managing geographically distributed systems with thousands of process variables. Tango Controls [@tango] offers similar capabilities with CORBA-based middleware. However, both frameworks prioritize network transparency and distributed operation, which introduces latency that can be problematic for high-speed feedback loops requiring sub-millisecond response times.

For laboratory-scale Python-based instrumentation, PyMoDAQ [@pymodaq] provides a modular approach to hardware control with a graphical user interface for experiment orchestration. While PyMoDAQ excels at general laboratory automation and data acquisition workflows, it is primarily designed for sequential measurement procedures rather than continuous high-speed feedback control. Its architecture focuses on scanner-based acquisition patterns, which differs fundamentally from the continuous streaming model required for adaptive optics and real-time control applications.

In the specific domain of astronomical adaptive optics, CACAO [@cacao] provides a high-performance real-time control system implementing efficient shared-memory data streams optimized for low-latency wavefront sensing and deformable mirror control. However, CACAO is tightly coupled to Linux-based real-time kernels and lacks cross-platform support, limiting its deployment flexibility. Furthermore, its focus on low-level control loops means it does not provide the instrument-level service architecture, configuration management, and hardware abstraction layers required for comprehensive testbed operation.

CATKit2 was developed to address the gap between these solutions by combining the best aspects of each approach. Compared to PyMoDAQ, CATKit2 focuses on high-speed continuous control systems with sub-millisecond latency requirements rather than sequential acquisition workflows. Its service-oriented architecture provides process isolation and fault tolerance critical for long-running experiments. Compared to CACAO, CATKit2 provides comprehensive instrument-level system design with modular services for diverse hardware types, unified configuration management, and cross-platform support for Windows, Linux, and macOS. The integrated simulation framework enables software-in-the-loop testing on any supported platform, facilitating collaborative development across institutions with different computing environments.

# Software design

The architecture of CATKit2 reflects careful trade-offs between performance, modularity, and ease of use. At the core of the system is the DataStream, a fixed-size circular buffer residing in shared memory that enables zero-copy data exchange between processes. DataFrames submitted to a DataStream receive unique identifiers and timestamps, enabling deterministic ordering and latency measurements. This design choice is critical for performance: because data resides in shared memory, multiple clients can access streaming data without involving the server process, eliminating the bottlenecks inherent in client-server architectures.

![CATKit2 system architecture showing the testbed server managing multiple services (cameras, deformable mirrors, stages) that communicate through shared memory data streams and ZeroMQ control channels. Clients access services through proxy objects that abstract the underlying communication mechanisms.\label{fig:architecture}](figure_1_architecture.png)

Building on this foundation, CATKit2 implements a service-oriented architecture where each hardware device or computational task runs as an independent process. This provides fault isolation—if one service crashes, others continue operating. The testbed server manages service dependencies and ensures that services start in the correct order. Each service exposes a consistent API consisting of properties (typed values with optional getters/setters), commands (remote procedure calls with named arguments), and data streams. This unified interface is accessible from both C++ and Python through proxy objects that hide the underlying communication complexity from users.

The communication stack employs a hybrid strategy optimized for different use cases. Protocol Buffers provide efficient binary message serialization with strong schema validation for control operations. ZeroMQ handles asynchronous request-reply and publish-subscribe messaging patterns. For high-bandwidth data streaming, the system bypasses the network stack entirely and uses shared memory directly. This combination optimizes for both low-latency control and high-throughput data transfer.

![Data stream latency measurements for a MacOS operating system (Apple M4 Max), demonstrating consistent sub-millisecond performance (similar results are obtained under Windows and Linux).  The mean latency on this system is 2.4 µs between sending a data frame from a Python service to receiving it in a different Python process, and below 13µs at 99.99% percentile. \label{fig:performance}](figure_2_data_latency_macos.png)

Configuration management is performed by the centralized TestbedServer. This configuration is distributed as JSON to all services and clients, ensuring consistent views of the testbed state. Services receive only their own configuration section, promoting encapsulation and reducing unintended cross-dependencies that can complicate maintenance.

Safety is a primary concern in hardware control systems. CATKit2 includes a safety service mechanism where designated services can monitor testbed conditions and trigger fail-safe states when unsafe conditions are detected. Services can declare safety dependencies, ensuring that they will not be started, or are stopped if a safety condition is triggered. This design provides defense in depth for expensive or delicate hardware components.

![End-to-end latency measurements for a typical adaptive optics control loop: wavefront sensor acquisition, processing, and deformable mirror command output.  Timing shown for Windows OS on the HiCAT testbed. 
This plot showss the total time from the earliest point in a command when it is emitted to the latest point when the receiver (here the camera) has fully settled to the command.  This total time includes the initial CATKit2 processing before it is sent to the DM API, then the DM Communication and DAC inside the control electonics, the actual mechanical response of the DM surface, the camera integration time, readout time, image transfer to computer, type conversion and copy to Data Stream.  In this example the mid point of the DM surface transition is at 1.7 ms and the DM has fully settled after 2.7 ms. \label{fig:timing}](figure_3_e2e_latency.png)

The server collects custom logging and tracing information from services and makes them available on a dedicated port. In particular, on-demand custom tracing is made available in the form of unified tracing file that can be vizualized by standard tools (e.g. Perfetto).  Tracing is simply implemented by adding a context manager around the section of the code that needs to be analyzed. Traces are available at the nanosecond level and special care has been taken to make sure this contributes negligible delay to code execution.          

![Example from the HiCAT testbed using Perfetto for vizualisation during a wavefront sensing and control experiment. Frames are read on camera and processed in a closed loop to calculate corrections applied on the DM. \label{fig:tracing}](figure_4_tracing.png)

# Research impact statement

CATKit2 has been in active development since 2022 and has been adopted by five astronomical instrumentation testbeds beyond its initial deployment on the HiCAT testbed at the Space Telescope Science Institute. These now include the Très Haute Dynamique (THD2) at Observatoire de Paris, the Santa Cruz Extreme AO Lab (SEAL) at University of California Santa Cruz, the Exoplanet Spectroscopy lab (ExoSpec) at Goddard Space Flight Center, and the High Contrast High-Resolution Spectroscopy for Segmented Telescopes Testbed (HCST) at Caltech. The framework has enabled research in high-contrast imaging, wavefront sensing, and adaptive optics, supporting the development of technologies relevant to future space-based exoplanet imaging missions.

By providing a robust simulation environment where hardware services can be replaced with software equivalents, CATKit2 has enabled researchers to validate control strategies before hardware implementation, significantly reducing development time and risk. This capability is particularly valuable for iterative algorithm development where rapid testing cycles are essential.

The package is released under the BSD 3-Clause license and is publicly available on GitHub. Documentation is hosted on GitHub Pages, including API references and configuration guides for bundled services. The modular service architecture has enabled contributions from multiple institutions, with new hardware services contributed by testbed operators at collaborating facilities. This collaborative development model has expanded the hardware support ecosystem while maintaining code quality through peer review and automated testing.

# AI usage disclosure

Generative AI tools (specifically GitHub Copilot, Qwen3 and Kimi K2.5) were used for code autocompletion and code generation during the development of this software, and drafting of this manuscript. All AI-generated code was subject to the same code review process as handwritten code, including stringent peer review via pull requests and validation through automated continuous integration tests.

# Acknowledgements

The authors thank the broader HiCAT team and the Space Telescope Science Institute for supporting this development. The HiCAT testbed has been developed over the past 10 years and benefitted from the work of an extended collaboration of over 50 people. This work was supported in part by the National Aeronautics and Space Administration under Grant 80NSSC19K0120 issued through the Strategic Astrophysics Technology/Technology Demonstration for Exo-planet Missions Program (SAT-TDEM; PI: R. Soummer), and under Grant 80NSSC22K0372 issued through the Astrophysics Research and Analysis Program (APRA; PI: L. Pueyo).
E.H.Por. was supported in part by the NASA Hubble Fellowship grant HST-HF2-51467.001-A awarded by the Space Telescope Science Institute, which is operated by the Association of Universities for Research in Astronomy, Incorporated, under NASA contract NAS5-26555. E.H.Por was also supported in part by a 51 Pegasi b Fellowship awarded by the Heising-Simons Foundation. S. Steiger acknowledges support by STScI Postdoctoral Fellowship and I. Laginja acknowledges partial support from a postdoctoral fellowship issued by the Centre National d’Etudes Spatiales (CNES) in France.

# References
