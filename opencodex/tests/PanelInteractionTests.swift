// Runs against the actual panel state machine, without opening a window or querying user data.
var assertions=0
func expect(_ condition:@autoclosure ()->Bool,_ message:String){assertions+=1;if !condition(){fatalError(message)}}
let fixture="""
{"dashboard":{"date":"","dates":[],"providers":[],"note":"","rangeKey":"today","rangeLabel":"当天","chartUnit":"","chartSpan":"","chartStatus":"","allowCollapse":true,"expandedProviders":[]},"entries":[],"moduleOptions":[{"label":"允许折叠","checked":true,"action":["set-collapse","false"],"children":[]}],"preferences":{"revision":1,"visible":["summary","opencodex","claude"],"appearance":"glass","allowCollapse":true,"expandedProviders":[]}}
"""
let initial=try JSONDecoder().decode(Snapshot.self,from:Data(fixture.utf8))
func saved(_ revision:Int64,_ expanded:[String])->PresentationPreferences{PresentationPreferences(revision:revision,visible:["summary","opencodex","claude"],appearance:"glass",allowCollapse:true,expandedProviders:expanded)}
func expanded(_ state:PanelInteraction)->Set<String>{Set(state.displayed()?.dashboard?.expandedProviders ?? [])}
var state=PanelInteraction(source:initial)
expect(state.submit(["set-expanded","opencodex","true"]) == .start,"First click must start")
expect(state.submit(["set-expanded","claude","true"]) == .queued,"Second module must queue")
expect(expanded(state)==Set(["opencodex","claude"]),"Both modules must expand immediately")
state.finish(saved(2,["opencodex"]))
state.source=initial // The old data render arrives after the save receipt.
expect(expanded(state)==Set(["opencodex","claude"]),"A stale render must not revert saved or queued state")
expect(state.next()==["set-expanded","claude","true"],"Queue must retain the next module")
expect(expanded(state)==Set(["opencodex","claude"]),"Starting queued action must not close the first module")
state.finish(saved(3,["opencodex","claude"]))
expect(expanded(state)==Set(["opencodex","claude"]),"Saved multiple expansions survive stale data")
expect(state.submit(["set-expanded","opencodex","false"]) == .start,"Close one module")
expect(expanded(state)==Set(["claude"]),"Closing one module must not close the other")
expect(state.submit(["set-expanded","opencodex","true"]) == .queued,"Rapid reopen queues")
expect(state.submit(["set-expanded","opencodex","false"]) == .queued,"Rapid reclose queues")
expect(expanded(state)==Set(["claude"]),"Newest click wins optimistically")
state.finish(saved(4,["claude"]))
_ = state.next() // Older reopen is now active, newer reclose remains queued.
expect(expanded(state)==Set(["claude"]),"Dispatching an older click must not override a newer queued click")
state.finish(saved(5,["opencodex","claude"]))
_ = state.next()
expect(expanded(state)==Set(["claude"]),"Last queued close still wins after the previous save")
state.finish(saved(6,["claude"]))
expect(state.next()==nil,"Queue drains")
var newer=initial;newer.preferences=saved(7,["opencodex"]);state.source=newer
expect(expanded(state)==Set(["opencodex"]),"Newer external settings override an older acknowledged state")
var busy=PanelInteraction(source:initial)
expect(busy.submit(["refresh-source","komari"]) == .start,"Resource check starts")
expect(busy.submit(["set-range","7d"]) == .queued,"Range click must not disappear during resource check")
expect(busy.submit(["open-settings"]) == .queued,"Menu action must not disappear during resource check")
expect(busy.submit(["open-settings"]) == .ignored,"Repeated non-preference action is not duplicated")
expect(busy.submit(["set-expanded","claude","true"]) == .queued,"Expansion during check queues")
expect(expanded(busy)==Set(["claude"]),"Expansion still responds immediately")
busy.finish(nil);expect(busy.next()==["set-range","7d"],"Range dispatches in order")
busy.finish(nil);expect(busy.next()==["open-settings"],"Menu action dispatches in order")
busy.finish(nil);expect(busy.next()==["set-expanded","claude","true"],"Expansion is eventually saved")
busy.finish(saved(2,["claude"]));expect(busy.next()==nil,"Background queue drains")
_ = busy.submit(["set-collapse","false"])
expect(busy.displayed()?.dashboard?.allowCollapse==false,"Disable collapse immediately")
expect(expanded(busy)==Set(["claude"]),"Disable collapse preserves independent state")
let scroll=ContentScrollView(frame:NSRect(x:0,y:0,width:200,height:150))
let document=FlippedView(frame:NSRect(x:0,y:0,width:200,height:100));scroll.documentView=document;scroll.configureScrolling()
expect(!scroll.needsVerticalScrolling,"Content that fits must not scroll")
expect(scroll.verticalScrollElasticity == .none,"Content that fits must not bounce")
let wheel=CGEvent(scrollWheelEvent2Source:nil,units:.pixel,wheelCount:1,wheel1:80,wheel2:0,wheel3:0)!
scroll.scrollWheel(with:NSEvent(cgEvent:wheel)!)
expect(scroll.contentView.bounds.origin == .zero,"Two-finger scroll must leave fitting content still")
document.setFrameSize(NSSize(width:200,height:500));scroll.configureScrolling()
expect(scroll.needsVerticalScrolling,"Overflow must remain scrollable")
scroll.contentView.scroll(to:NSPoint(x:0,y:120));document.setFrameSize(NSSize(width:200,height:100));scroll.configureScrolling()
expect(scroll.contentView.bounds.origin == .zero,"Collapsing content must clear obsolete scroll offset")
expect(!scroll.hasVerticalScroller,"No scrollbar when everything fits")
print("Native interaction assertions: \(assertions) passed")
