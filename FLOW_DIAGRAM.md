# X-Interact Tracker - Flow Diagram

## 1. Application Startup Flow

```mermaid
graph TD
    A[Start Application] --> B[Load Environment Variables]
    B --> C[Initialize Settings]
    C --> D[Setup Signal Handlers]
    D --> E[Initialize AccountManager]
    E --> F[Load accounts.json]
    F --> G{Proxy Rotation Enabled?}
    G -->|Yes| H[Start Health Checker Thread]
    G -->|No| I[Skip Health Checker]
    H --> J[Load Previous State]
    I --> J
    J --> K[Resolve Users with First Healthy Account]
    K --> L{Users Resolved Successfully?}
    L -->|No| M[Runtime Error - Abort]
    L -->|Yes| N{Bootstrap Mode?}
    N -->|Yes| O[Set Baseline Tweet IDs]
    N -->|No| P[Skip Baseline]
    O --> Q[Save Initial State]
    P --> R[Create Persistent Thread Pool]
    Q --> R
    R --> S[Enter Main Polling Loop]
```

## 2. Main Polling Loop Flow

```mermaid
graph TD
    A[Main Loop Start] --> B{Shutdown Event Set?}
    B -->|Yes| C[Graceful Shutdown]
    B -->|No| D[Create Result Queue]
    D --> E[Submit User Tasks to Thread Pool]
    E --> F[Wait for All Tasks Complete]
    F --> G[Process Results from Queue]
    G --> H{New Tweets Found?}
    H -->|Yes| I[Send Webhooks for New Tweets]
    H -->|No| J[Skip Webhook Sending]
    I --> K[Update State with New Tweet IDs]
    J --> L[Save Account Health Status]
    K --> M[Save State to File]
    L --> N{State Changed?}
    M --> N
    N -->|Yes| O[Save State File]
    N -->|No| P[Skip State Save]
    O --> Q[Wait for Poll Interval]
    P --> Q
    Q --> B
```

## 3. User Tweet Processing Flow

```mermaid
graph TD
    A[Process User Tweets Task] --> B[Get Next Available Account]
    B --> C{Account Available?}
    C -->|No| D[Queue Error - No Accounts]
    C -->|Yes| E[Check Rate Limit]
    E --> F{Account Rate Limited?}
    F -->|Yes| G[Skip to Next Account]
    F -->|No| H[Record Request Timestamp]
    H --> I[Initialize Scraper if Needed]
    I --> J[Get User State]
    J --> K[Fetch Latest Tweets]
    K --> L{Tweets Found?}
    L -->|No| M[Queue Success - No Tweets]
    L -->|Yes| N[Extract & Normalize Tweet Data]
    N --> O[Sort Tweets by ID]
    O --> P[Compare with Last Seen ID]
    P --> Q[Find New Tweets]
    Q --> R[Queue Success with New Tweets]
    R --> S[Mark Account as Successful]
    S --> T[Task Complete]
    M --> T
    G --> B
    D --> T
```

## 4. Error Handling & Retry Flow

```mermaid
graph TD
    A[Exception Occurred] --> B[Log Error Message]
    B --> C[Mark Account as Failed]
    C --> D{Last Retry Attempt?}
    D -->|Yes| E[Queue Error Result]
    D -->|No| F[Calculate Exponential Backoff Delay]
    F --> G[Add Random Jitter]
    G --> H[Wait for Delay]
    H --> I[Retry with Different Account]
    I --> J[Back to Processing]
    E --> K[Task Complete with Error]
```

## 5. Proxy Health Checker Flow

```mermaid
graph TD
    A[Health Checker Thread Start] --> B{Shutdown Event Set?}
    B -->|Yes| C[Exit Gracefully]
    B -->|No| D[Wait for Health Check Interval]
    D --> E{Shutdown Event During Wait?}
    E -->|Yes| C
    E -->|No| F[Iterate Through All Accounts]
    F --> G{Account Enabled & Proxy Enabled?}
    G -->|No| H[Skip Account]
    G -->|Yes| I[Test Proxy Connection]
    I --> J{Proxy Test Successful?}
    J -->|Yes| K[Mark Account as Successful]
    J -->|No| L[Mark Account as Failed]
    K --> M[Next Account]
    L --> M
    H --> M
    M --> N{More Accounts?}
    N -->|Yes| G
    N -->|No| O[Save Account Health Status]
    O --> P[Error in Health Check?]
    P -->|Yes| Q[Wait 60 seconds]
    P -->|No| B
    Q --> B
```

## 6. Graceful Shutdown Flow

```mermaid
graph TD
    A[Signal Received SIGINT/SIGTERM] --> B[Set Shutdown Event]
    B --> C[Print Shutdown Message]
    C --> D[Exit Current Process]
    D --> E[Main Loop Detects Shutdown Event]
    E --> F[Break from Polling Loop]
    F --> G[Shutdown Thread Pool]
    G --> H[Wait for Thread Pool Completion]
    H --> I{Health Thread Running?}
    I -->|Yes| J[Wait for Health Thread]
    I -->|No| K[Skip Health Thread Wait]
    J --> L{Health Thread Timeout?}
    L -->|Yes| M[Force Continue]
    L -->|No| N[Health Thread Complete]
    M --> O[Print Shutdown Complete]
    N --> O
    K --> O
    O --> P[Application Exit]
```

## 7. State Management Flow

```mermaid
graph TD
    A[State Operation] --> B{Lock Required?}
    B -->|Yes| C[Acquire State Lock]
    B -->|No| D[Proceed Directly]
    C --> E[Perform State Operation]
    D --> E
    E --> F{Operation Successful?}
    F -->|Yes| G[Write to Temporary File]
    F -->|No| H[Log Error]
    G --> I[Atomic Replace Original File]
    I --> J{Lock Acquired?}
    J -->|Yes| K[Release Lock]
    J -->|No| L[Continue]
    H --> L
    K --> L
    L --> M[Operation Complete]
```

## 8. Account Rotation Flow

```mermaid
graph TD
    A[Request Next Account] --> B[Acquire Account Lock]
    B --> C[Filter Healthy Accounts]
    C --> D{Healthy Accounts Available?}
    D -->|No| E[Return None]
    D -->|Yes| F{Rotation Strategy}
    F -->|Round Robin| G[Select by Current Index]
    F -->|Random| H[Select Random Account]
    F -->|Other| I[Select First Account]
    G --> J[Increment Current Index]
    J --> K[Release Account Lock]
    H --> K
    I --> K
    K --> L[Return Selected Account]
    E --> M[Release Account Lock]
    M --> N[Return None]
```

## Key Components Interaction

```mermaid
graph TB
    subgraph "Main Thread"
        A[Main Loop]
        B[Result Processing]
        C[State Management]
    end
    
    subgraph "Thread Pool"
        D[Worker Thread 1]
        E[Worker Thread N]
        F[Task Queue]
    end
    
    subgraph "Background Threads"
        G[Health Checker Thread]
    end
    
    subgraph "Shared Resources"
        H[Account Manager]
        I[State File]
        J[Accounts Config]
        K[Result Queue]
    end
    
    A --> F
    F --> D
    F --> E
    D --> K
    E --> K
    K --> B
    B --> C
    C --> I
    A --> H
    G --> H
    H --> J
    D --> H
    E --> H
```

## Thread Safety Mechanisms

```mermaid
graph TD
    A[Thread Safety Components] --> B[Account Lock]
    A --> C[State Lock]
    A --> D[Scraper Lock]
    A --> E[Thread-Safe Queue]
    
    B --> F[Protects Account Selection]
    B --> G[Protects Health Status Updates]
    
    C --> H[Protects State File I/O]
    C --> I[Atomic File Operations]
    
    D --> J[Protects Scraper Initialization]
    D --> K[Prevents Concurrent Scraper Access]
    
    E --> L[Thread-Safe Result Collection]
    E --> M[Prevents Race Conditions]
```

## Performance Optimizations

```mermaid
graph TD
    A[Performance Features] --> B[Deque for Rate Limiting]
    A --> C[Connection Pooling]
    A --> D[Persistent Thread Pool]
    A --> E[Smart State Saving]
    
    B --> F[O(1) Rate Limit Checks]
    B --> G[Automatic Memory Cleanup]
    
    C --> H[Reduced TCP Overhead]
    C --> I[Connection Reuse]
    
    D --> J[No Thread Creation Overhead]
    D --> K[Resource Reuse]
    
    E --> L[Save Only When Changed]
    E --> M[Reduced Disk I/O]