import AppKit
import Foundation
import UserNotifications

final class NotificationPresenter: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }
}

guard CommandLine.arguments.count == 5 else { exit(1) }
let outputURL = URL(fileURLWithPath: CommandLine.arguments[1])
func writeResult(_ result: String) {
    try? result.write(to: outputURL, atomically: true, encoding: .utf8)
}

let center = UNUserNotificationCenter.current()
let presenter = NotificationPresenter()
center.delegate = presenter
let authorizationDone = DispatchSemaphore(value: 0)
var authorized = false
center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
    authorized = granted
    authorizationDone.signal()
}
authorizationDone.wait()
guard authorized else {
    writeResult("NOTIFICATION_DENIED\n")
    exit(2)
}

let content = UNMutableNotificationContent()
content.title = CommandLine.arguments[2]
content.body = CommandLine.arguments[3]
content.sound = .default
if CommandLine.arguments[4] == "urgent" {
    content.interruptionLevel = .timeSensitive
}
let request = UNNotificationRequest(
    identifier: UUID().uuidString, content: content, trigger: nil)
let deliveryDone = DispatchSemaphore(value: 0)
var delivered = false
center.add(request) { error in
    delivered = error == nil
    deliveryDone.signal()
}
deliveryDone.wait()
writeResult(delivered ? "NOTIFICATION_SENT\n" : "NOTIFICATION_FAILED\n")
if delivered && CommandLine.arguments[4] == "urgent" {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let width: CGFloat = 390
    let height: CGFloat = 96
    let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    let frame = NSRect(x: screen.maxX - width - 18, y: screen.maxY - height - 18,
                       width: width, height: height)
    let panel = NSPanel(contentRect: frame, styleMask: [.borderless, .nonactivatingPanel],
                        backing: .buffered, defer: false)
    panel.isOpaque = false
    panel.backgroundColor = .clear
    panel.hasShadow = true
    panel.level = .statusBar
    panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
    let background = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
    background.wantsLayer = true
    background.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
    background.layer?.cornerRadius = 14
    background.layer?.borderWidth = 1
    background.layer?.borderColor = NSColor.separatorColor.cgColor
    let accent = NSView(frame: NSRect(x: 0, y: 0, width: 6, height: height))
    accent.wantsLayer = true
    accent.layer?.backgroundColor = (content.title.contains("warning")
                                      ? NSColor.systemYellow : NSColor.systemRed).cgColor
    background.addSubview(accent)
    let title = NSTextField(labelWithString: content.title)
    title.frame = NSRect(x: 23, y: 53, width: width - 42, height: 26)
    title.font = .boldSystemFont(ofSize: 16)
    background.addSubview(title)
    let message = NSTextField(wrappingLabelWithString: content.body)
    message.frame = NSRect(x: 23, y: 13, width: width - 42, height: 39)
    message.font = .systemFont(ofSize: 13)
    background.addSubview(message)
    panel.contentView = background
    panel.orderFrontRegardless()
    RunLoop.current.run(until: Date().addingTimeInterval(10))
} else {
    RunLoop.current.run(until: Date().addingTimeInterval(3))
}
exit(delivered ? 0 : 3)
