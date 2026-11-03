import EventKit
import Foundation

let watching = CommandLine.arguments.count == 5 && CommandLine.arguments[1] == "watch"
guard watching || CommandLine.arguments.count == 3 else {
    fputs("CALENDAR_NAME_AND_OUTPUT_REQUIRED\n", stderr)
    exit(1)
}

let outputURL = URL(fileURLWithPath: CommandLine.arguments[watching ? 3 : 2])
func writeResult(_ result: String) {
    guard let data = result.data(using: .utf8) else { exit(1) }
    do {
        try data.write(to: outputURL, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600],
                                              ofItemAtPath: outputURL.path)
    } catch {
        fputs("OUTPUT_WRITE_FAILED\n", stderr)
        exit(1)
    }
}

if watching {
    let pidURL = URL(fileURLWithPath: CommandLine.arguments[4])
    try? String(ProcessInfo.processInfo.processIdentifier).write(
        to: pidURL, atomically: true, encoding: .utf8)
}

let store = EKEventStore()
let authorization = EKEventStore.authorizationStatus(for: .event)
if authorization != .fullAccess {
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    store.requestFullAccessToEvents { allowed, _ in
        granted = allowed
        semaphore.signal()
    }
    semaphore.wait()
    if !granted {
        writeResult("CALENDAR_ACCESS_DENIED\n")
        exit(2)
    }
}

let calendarName = CommandLine.arguments[watching ? 2 : 1]
guard let calendar = store.calendars(for: .event).first(where: { $0.title == calendarName }) else {
    writeResult("CALENDAR_NOT_FOUND\n")
    exit(0)
}

func updateReadings() {
    store.refreshSourcesIfNecessary()
    let now = Date()
    let predicate = store.predicateForEvents(
        withStart: now.addingTimeInterval(-24 * 60 * 60),
        end: now.addingTimeInterval(5 * 60),
        calendars: [calendar]
    )
    var lines: [String] = []
    for event in store.events(matching: predicate) {
        let title = (event.title ?? "")
            .replacingOccurrences(of: "\t", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\r", with: " ")
        let secondsOld = Int(now.timeIntervalSince(event.startDate))
        lines.append("\(title)\t\(secondsOld)")
    }
    writeResult(lines.joined(separator: "\n") + "\n")
}

if watching {
    while true {
        updateReadings()
        Thread.sleep(forTimeInterval: 60)
    }
} else {
    updateReadings()
}
