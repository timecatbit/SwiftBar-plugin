import AppKit
import CoreGraphics

struct Entry: Decodable {
    var label:String;var separator:Bool?;var image:String?;var template:Bool?;var symbol:String?
    var section:Bool?;var attention:Bool?;var checked:Bool?;var detail:String?;var value:String?;var href:String?;var action:[String]?;var children:[Entry]
    var actionable:Bool { !children.isEmpty || href != nil || action != nil }
    var key:String {action?.joined(separator:"\u{001F}") ?? href ?? label.components(separatedBy:" · ").first ?? label}
}
struct ModelUsage:Decodable {var name:String;var tokens:Double;var share:Double}
struct ProviderUsage:Decodable {
    var id:String;var name:String;var subtitle:String;var status:String;var available:Bool
    var cost:Double?;var tokens:Double;var requests:Int;var output:Double;var cache:Double?;var coverage:Double?
    var sessions:Int;var unpriced:Int;var summaryIncluded:Bool?;var models:[ModelUsage];var history:[Double]
}
struct Dashboard:Decodable {var date:String;var dates:[String];var providers:[ProviderUsage];var note:String;var rangeKey:String;var rangeLabel:String;var chartUnit:String;var chartSpan:String;var chartStatus:String;var chartPositions:[Double]?;var showSummary:Bool?}
struct Snapshot:Decodable {var dashboard:Dashboard?;var entries:[Entry];var rangeOptions:[Entry]?;var updateCount:Int?;var moduleOptions:[Entry]?;var appearance:String?}
func dark(_ view:NSView)->Bool {view.effectiveAppearance.bestMatch(from:[.darkAqua,.aqua]) == .darkAqua}
func background(_ view:NSView)->NSColor {dark(view) ? NSColor(calibratedWhite:0.115,alpha:1) : NSColor(calibratedWhite:0.992,alpha:1)}
func accent(_ id:String,_ view:NSView)->NSColor {
    if id=="claude" {return dark(view) ? NSColor(srgbRed:0.91,green:0.65,blue:0.46,alpha:1) : NSColor(srgbRed:0.75,green:0.40,blue:0.25,alpha:1)}
    if id=="codex" {return .systemPurple}
    if id=="opencode" {return .systemPink}
    if id=="workbuddy" {return .systemOrange}
    if id=="gemini" {return .systemTeal}
    if id=="deepseek-harness" {return .systemIndigo}
    return dark(view) ? NSColor(srgbRed:0.55,green:0.71,blue:0.94,alpha:1) : NSColor(srgbRed:0.32,green:0.51,blue:0.78,alpha:1)
}
func statusGreen(_ view:NSView)->NSColor {dark(view) ? NSColor(srgbRed:0.49,green:0.79,blue:0.61,alpha:1) : NSColor(srgbRed:0.18,green:0.49,blue:0.31,alpha:1)}
func share(_ ratio:Double)->String {let value=ratio*100;return String(format:(value>0 && value<1)||(value>99 && value<100) ? "%.1f%%" : "%.0f%%",value)}
func tokens(_ value:Double)->String {
    if value>=1e9{return String(format:"%.2fB",value/1e9)}
    if value>=1e6{return String(format:"%.2fM",value/1e6)}
    if value>=1e3{return String(format:"%.1fK",value/1e3)}
    return String(format:"%.0f",value)
}
func axisTokens(_ value:Double)->String {
    for (unit,suffix) in [(1e9,"B"),(1e6,"M"),(1e3,"K")] where value>=unit {
        let scaled=value/unit
        return String(format:scaled>=10 || scaled==floor(scaled) ? "%.0f%@" : "%.1f%@",scaled,suffix)
    }
    return String(format:"%.0f",value)
}
func modelName(_ name:String)->String {
    guard name.hasPrefix("claude-") else{return name}
    let value=name.replacingOccurrences(of:"-20[0-9]{6}$",with:"",options:.regularExpression)
    let parts=value.dropFirst(7).split(separator:"-").map(String.init)
    guard let family=parts.first,["opus","sonnet","haiku","fable"].contains(family) else{return name}
    return family.capitalized+" "+parts.dropFirst().joined(separator:".")
}
func money(_ value:Double?)->String {value.map{String(format:"$%.2f",$0)} ?? "—"}
func text(_ value:String,x:CGFloat,y:CGFloat,w:CGFloat,size:CGFloat=11,color:NSColor = .labelColor,weight:NSFont.Weight = .regular,align:NSTextAlignment = .left,numeric:Bool=false) {
    let style=NSMutableParagraphStyle();style.alignment=align;style.lineBreakMode = .byTruncatingTail
    var font=numeric ? NSFont.monospacedDigitSystemFont(ofSize:size,weight:weight) : NSFont.systemFont(ofSize:size,weight:weight)
    if numeric {let measured=(value as NSString).size(withAttributes:[.font:font]).width;if measured>w {font=NSFont.monospacedDigitSystemFont(ofSize:max(9,size*w/measured),weight:weight)}}
    (value as NSString).draw(in:NSRect(x:x,y:y,width:w,height:size+6),withAttributes:[.font:font,.foregroundColor:color,.paragraphStyle:style])
}
func line(_ a:NSPoint,_ b:NSPoint,color:NSColor = .separatorColor,width:CGFloat=0.5) {
    let p=NSBezierPath();p.move(to:a);p.line(to:b);p.lineWidth=width;color.setStroke();p.stroke()
}
class FlippedView:NSView {override var isFlipped:Bool {true}}
final class Surface:FlippedView {
    let content:FlippedView
    private let translucent:Bool
    init(frame:NSRect,glass:Bool=true){
        content=FlippedView(frame:NSRect(origin:.zero,size:frame.size))
        translucent=glass && !NSWorkspace.shared.accessibilityDisplayShouldReduceTransparency
        super.init(frame:frame);wantsLayer=true;layer?.cornerRadius=13;layer?.masksToBounds=true
        content.autoresizingMask=[.width,.height]
        if translucent {
            #if compiler(>=6.2)
            if #available(macOS 26.0,*) {
                let effect=NSGlassEffectView(frame:bounds);effect.style = .regular;effect.cornerRadius=13
                effect.autoresizingMask=[.width,.height];effect.contentView=content;addSubview(effect)
                return
            }
            #endif
            let effect=NSVisualEffectView(frame:bounds);effect.material = .popover;effect.blendingMode = .behindWindow
            effect.state = .active;effect.autoresizingMask=[.width,.height];effect.addSubview(content);addSubview(effect)
        } else {addSubview(content)}
    }
    required init?(coder:NSCoder){fatalError()}
    override func viewDidChangeEffectiveAppearance(){super.viewDidChangeEffectiveAppearance();redraw(self)}
    private func redraw(_ view:NSView){view.needsDisplay=true;for child in view.subviews{redraw(child)}}
    override func draw(_ dirtyRect:NSRect){
        if !translucent {background(self).setFill();bounds.fill()}
        let shape=NSBezierPath(roundedRect:bounds.insetBy(dx:0.25,dy:0.25),xRadius:13,yRadius:13)
        NSColor.separatorColor.withAlphaComponent(0.35).setStroke();shape.lineWidth=0.5;shape.stroke()
    }
}
final class Panel:NSPanel {
    var escape:(()->Void)?
    override var canBecomeKey:Bool {true}
    override func keyDown(with event:NSEvent){if event.keyCode==53{escape?()}else{super.keyDown(with:event)}}
}
final class DashboardView:FlippedView {
    var data:Dashboard
    private var summaryProviders:[ProviderUsage] {data.providers.filter{$0.summaryIncluded != false}}
    static func sectionHeight(_ p:ProviderUsage)->CGFloat {122+CGFloat(max(1,p.models.count))*18}
    static func chartExtra(_ d:Dashboard)->CGFloat {CGFloat(max(0,(d.providers.filter{$0.summaryIncluded != false}.count+3)/3-1))*17}
    static func summaryHeight(_ d:Dashboard)->CGFloat {d.showSummary==false ? 44 : 254+chartExtra(d)}
    static func height(_ d:Dashboard)->CGFloat {summaryHeight(d)+d.providers.reduce(0){$0+sectionHeight($1)}+22}
    init(_ data:Dashboard,width:CGFloat){self.data=data;super.init(frame:NSRect(x:0,y:0,width:width,height:Self.height(data)));setAccessibilityElement(false);setAccessibilityRole(.group);setAccessibilityLabel("Summary. "+data.providers.map{"\($0.name): \(money($0.cost)), \(tokens($0.tokens)) Token, \($0.requests) 次请求"}.joined(separator:". "))}
    required init?(coder:NSCoder){fatalError()}
    override func viewDidChangeEffectiveAppearance(){super.viewDidChangeEffectiveAppearance();needsDisplay=true}
    override func draw(_ dirtyRect:NSRect){
        let left:CGFloat=12,right=bounds.width-12,width=right-left
        let valid=summaryProviders.filter{$0.available},costs=valid.compactMap{$0.cost}
        text(data.showSummary==false ? "用量" : "Summary",x:left,y:10,w:150,size:14,weight:.semibold)
        if data.showSummary != false {
        let partial=valid.count != summaryProviders.count || valid.contains{$0.unpriced>0}
        let columns:[CGFloat]=[width*0.38,width*0.38,width*0.24]
        let labels=[partial ? "已知 API 估算" : "API 估算","Token 用量","请求"]
        let values=[money(costs.isEmpty ? nil : costs.reduce(0,+)),valid.isEmpty ? "—" : tokens(valid.reduce(0){$0+$1.tokens}),valid.isEmpty ? "—" : String(valid.reduce(0){$0+$1.requests})]
        for i in 0..<3 {let column=columns[i],x=left+columns.prefix(i).reduce(0,+);text(labels[i],x:x,y:40,w:column-8,size:10,color:.secondaryLabelColor);text(values[i],x:x,y:56,w:column-6,size:i==2 ? 20 : 21,weight:.medium,numeric:true)}
        drawSummaryChart(left:left,right:right)
        }
        var y:CGFloat=Self.summaryHeight(data)
        for p in data.providers {drawProvider(p,y:y,left:left,right:right);y+=Self.sectionHeight(p)}
        text(data.note,x:left,y:y+3,w:width,size:8.5,color:.secondaryLabelColor)
    }
    private func drawProvider(_ p:ProviderUsage,y:CGFloat,left:CGFloat,right:CGFloat){
        let width=right-left,c=accent(p.id,self)
        c.setFill();NSBezierPath(ovalIn:NSRect(x:left,y:y+14,width:5,height:5)).fill()
        text(p.name,x:left+12,y:y+8,w:width-140,size:12,weight:.semibold)
        let status=p.available ? p.status : (p.status=="运行正常" ? "数据暂不可用" : p.status)
        text(status,x:right-130,y:y+10,w:130,size:9,color:status=="运行正常" || status=="已同步" ? statusGreen(self) : .secondaryLabelColor,align:.right)
        text(p.subtitle,x:left+12,y:y+26,w:width-12,size:9,color:.secondaryLabelColor)
        text(p.available ? money(p.cost) : "—",x:left,y:y+45,w:width*0.43,size:19,weight:.medium,numeric:true)
        text(p.available ? tokens(p.tokens)+" Token" : "—",x:left+width*0.43,y:y+47,w:width*0.57,size:16,weight:.medium,align:.right,numeric:true)
        let cache=p.cache.map{String(format:"%.1f%% 缓存",$0*100)} ?? "缓存 —"
        let meta=p.available ? "\(p.requests) 请求 · \(cache)" : "等待可用数据"
        var extra=p.available ? "输出 \(tokens(p.output))" : ""
        if p.id != "opencodex" && p.available {extra += " · \(p.sessions) 会话"}
        if p.id=="opencodex",p.available,let coverage=p.coverage,coverage<1 {extra += String(format:" · 计费覆盖 %.0f%%",coverage*100)}
        text(meta,x:left,y:y+72,w:width,size:10,color:.secondaryLabelColor)
        text(extra,x:left,y:y+87,w:width,size:9.5,color:.secondaryLabelColor)
        if p.models.isEmpty {text(p.available ? "此时段暂无模型调用" : "模型明细暂不可用",x:left,y:y+106,w:width,size:10.5,color:.secondaryLabelColor)}
        for (i,m) in p.models.enumerated(){
            let top=y+106+CGFloat(i)*18
            text(modelName(m.name),x:left,y:top,w:width-120,size:10.5)
            text(tokens(m.tokens),x:right-115,y:top,w:72,size:10.5,align:.right,numeric:true)
            text(share(m.share),x:right-38,y:top,w:38,size:10,color:.secondaryLabelColor,align:.right,numeric:true)
            NSColor.quaternaryLabelColor.withAlphaComponent(0.12).setFill();NSRect(x:left,y:top+14,width:width,height:1.5).fill()
            c.withAlphaComponent(0.55).setFill();NSRect(x:left,y:top+14,width:width*CGFloat(m.share),height:1.5).fill()
        }
    }
    private func drawSummaryChart(left:CGFloat,right:CGFloat){
        let width=right-left,n=data.dates.count
        guard n>0 else{return}
        let series=summaryProviders.map{p in (0..<n).map{i in i<p.history.count ? max(0,p.history[i]) : 0}}
        let totals=(0..<n).map{i in series.reduce(0){$0+$1[i]}}
        let totalColor=dark(self) ? NSColor(srgbRed:0.43,green:0.79,blue:0.75,alpha:1) : NSColor(srgbRed:0.15,green:0.47,blue:0.46,alpha:1)
        text("Token 趋势 · "+data.chartUnit,x:left,y:98,w:135,size:9.5,color:.secondaryLabelColor)
        text(data.chartSpan,x:left+125,y:99,w:width-125,size:8.5,color:.secondaryLabelColor,align:.right)
        let legend:[(String,NSColor)]=[("总量",totalColor)]+summaryProviders.map{($0.id=="claude" ? "Claude" : $0.name,accent($0.id,self))}
        for (i,entry) in legend.enumerated(){
            let columns=min(3,legend.count),cell=width/CGFloat(columns),x=left+CGFloat(i%columns)*cell,y=CGFloat(i/columns)*17
            entry.1.setFill();NSBezierPath(roundedRect:NSRect(x:x,y:120+y,width:11,height:i==0 ? 3 : 2),xRadius:1.5,yRadius:1.5).fill()
            text(entry.0,x:x+17,y:114+y,w:cell-20,size:8.5,color:.secondaryLabelColor)
        }
        NSGraphicsContext.saveGraphicsState()
        defer{NSGraphicsContext.restoreGraphicsState()}
        NSGraphicsContext.current?.cgContext.translateBy(x:0,y:Self.chartExtra(data))
        let observed=max(totals.max() ?? 0,1),unit=pow(10,floor(log10(observed)))
        let ceiling=ceil(observed*1.08/unit*2)/2*unit
        let plot=NSRect(x:left+32,y:143,width:width-36,height:78)
        let card=NSBezierPath(roundedRect:NSRect(x:left+27,y:135,width:width-27,height:90),xRadius:7,yRadius:7)
        totalColor.withAlphaComponent(dark(self) ? 0.035 : 0.025).setFill();card.fill()
        for f in [CGFloat(0),0.5,1]{
            let yy=plot.maxY-f*plot.height
            text(axisTokens(ceiling*Double(f)),x:left-2,y:yy-5,w:27,size:8,color:.secondaryLabelColor,align:.right,numeric:true)
            line(NSPoint(x:plot.minX,y:yy),NSPoint(x:plot.maxX,y:yy),color:NSColor.separatorColor.withAlphaComponent(0.22),width:0.5)
        }
        if n==1 {
            for (i,values) in series.enumerated(){let y=plot.maxY-CGFloat(values[0]/ceiling)*plot.height;accent(summaryProviders[i].id,self).setFill();NSBezierPath(ovalIn:NSRect(x:plot.midX-2.5,y:y-2.5,width:5,height:5)).fill()}
            let y=plot.maxY-CGFloat(totals[0]/ceiling)*plot.height;totalColor.setFill();NSBezierPath(ovalIn:NSRect(x:plot.midX-3,y:y-3,width:6,height:6)).fill()
            text(data.dates[0],x:plot.midX-30,y:228,w:60,size:8.5,color:.secondaryLabelColor,align:.center)
            line(NSPoint(x:left,y:246),NSPoint(x:right,y:246));return
        }
        let positions: [Double]
        if let values=data.chartPositions,values.count==n,values.allSatisfy({$0.isFinite}),zip(values,values.dropFirst()).allSatisfy({$0<$1}) {positions=values}
        else{positions=(0..<n).map{Double($0)/Double(n-1)}}
        let intervals=(0..<n-1).map{positions[$0+1]-positions[$0]}
        // Linear slopes are shared by all series: the smoothed total equals
        // the sum of the two provider curves at every point, including between days.
        func slopes(_ values:[Double])->[Double]{
            let d=(0..<n-1).map{(values[$0+1]-values[$0])/intervals[$0]}
            var result=[Double](repeating:0,count:n)
            result[0]=d[0];result[n-1]=d[n-2]
            if n>2{for i in 1..<n-1{result[i]=(d[i-1]+d[i])/3}}
            return result
        }
        let shapeSeries=series+[totals]
        var tangents=shapeSeries.map{slopes($0)}
        // Apply one common limiter per day, preserving additivity while
        // preventing either provider line from overshooting its observations.
        for i in 0..<n {
            var factor=1.0
            for (j,values) in shapeSeries.enumerated(){
                let t=tangents[j][i]
                for k in [i-1,i] where k>=0 && k<n-1 {
                    let d=(values[k+1]-values[k])/intervals[k]
                    if d==0 || t*d<0{factor=0}else if abs(t)>0{factor=min(factor,abs(3*d/t))}
                }
            }
            for j in tangents.indices{tangents[j][i]*=factor}
        }
        for i in 0..<n-1 {
            var factor=1.0
            for (j,values) in shapeSeries.enumerated(){let delta=values[i+1]-values[i];if delta != 0 {let a=tangents[j][i]*intervals[i]/delta,b=tangents[j][i+1]*intervals[i]/delta,s=a*a+b*b;if s>9{factor=min(factor,3/sqrt(s))}}}
            for j in tangents.indices{tangents[j][i]*=factor;tangents[j][i+1]*=factor}
        }
        let totalTangents=tangents.last!
        func path(_ values:[Double],_ slopes:[Double])->NSBezierPath {
            let scale=plot.height/CGFloat(ceiling)
            let points=values.enumerated().map{NSPoint(x:plot.minX+CGFloat(positions[$0.offset])*plot.width,y:plot.maxY-CGFloat($0.element)*scale)}
            let curve=NSBezierPath();curve.move(to:points[0])
            for i in 0..<n-1{let dt=CGFloat(intervals[i]),dx=plot.width*dt;curve.curve(to:points[i+1],controlPoint1:NSPoint(x:points[i].x+dx/3,y:points[i].y-CGFloat(slopes[i])*dt*scale/3),controlPoint2:NSPoint(x:points[i+1].x-dx/3,y:points[i+1].y+CGFloat(slopes[i+1])*dt*scale/3))}
            return curve
        }
        let totalPath=path(totals,totalTangents)
        let area=totalPath.copy() as! NSBezierPath;area.line(to:NSPoint(x:plot.maxX,y:plot.maxY));area.line(to:NSPoint(x:plot.minX,y:plot.maxY));area.close()
        NSGraphicsContext.saveGraphicsState();area.addClip();NSGradient(starting:totalColor.withAlphaComponent(dark(self) ? 0.10 : 0.07),ending:totalColor.withAlphaComponent(0.005))?.draw(from:NSPoint(x:plot.midX,y:plot.minY),to:NSPoint(x:plot.midX,y:plot.maxY),options:[]);NSGraphicsContext.restoreGraphicsState()
        let curves=summaryProviders.enumerated().map{(series[$0.offset],tangents[$0.offset],accent($0.element.id,self),CGFloat(1.45))}+[(totals,totalTangents,totalColor,CGFloat(2.0))]
        for (values,slopes,color,weight) in curves{
            let curve=path(values,slopes);curve.lineWidth=weight;curve.lineCapStyle = .round;curve.lineJoinStyle = .round;color.setStroke();curve.stroke()
        }
        let middle=(1..<n-1).filter{positions[$0]>=0.25 && positions[$0]<=0.75}.min{abs(positions[$0]-0.5)<abs(positions[$1]-0.5)}
        let labelIndices=[0]+(middle.map{[$0]} ?? [])+[n-1]
        for i in labelIndices{let label=data.dates[i];let x=plot.minX+CGFloat(positions[i])*plot.width;text(label,x:i==0 ? x : (i==n-1 ? x-48 : x-25),y:228,w:i==n-1 ? 48 : 50,size:8.5,color:.secondaryLabelColor,align:i==0 ? .left : (i==n-1 ? .right : .center))}
        if !data.chartStatus.isEmpty {text(data.chartStatus,x:left+37,y:171,w:width-45,size:10,color:.secondaryLabelColor,align:.center)}
        line(NSPoint(x:left,y:246),NSPoint(x:right,y:246))
    }

}
enum MenuLayout {
    static func hasIcon(_ e:Entry)->Bool {e.image != nil || e.symbol != nil || e.checked != nil}
    static func column(_ entries:[Entry])->CGFloat {entries.contains(where:hasIcon) ? 36 : 12}
    static func labelFont(_ e:Entry)->NSFont {.systemFont(ofSize:e.section==true ? 10.5 : (e.actionable ? 12 : 10.5),weight:e.section==true ? .medium : .regular)}
    static let valueFont=NSFont.monospacedDigitSystemFont(ofSize:11,weight:.regular)
    static let detailFont=NSFont.systemFont(ofSize:10)
    static func width(_ value:String,font:NSFont)->CGFloat {ceil((value as NSString).size(withAttributes:[.font:font]).width)}
    static func height(_ value:String,font:NSFont,width:CGFloat)->CGFloat {
        ceil((value as NSString).boundingRect(with:NSSize(width:max(1,width),height:1000),options:[.usesLineFragmentOrigin,.usesFontLeading],attributes:[.font:font]).height)
    }
    static func valueWidth(_ e:Entry)->CGFloat {e.value.map{width($0,font:valueFont)+(e.attention==true ? 16 : 0)} ?? 0}
    static func trailing(_ e:Entry)->CGFloat {e.children.isEmpty ? 12 : 32}
    static func labelWidth(_ e:Entry,width:CGFloat,left:CGFloat)->CGFloat {max(24,width-left-trailing(e)-valueWidth(e)-(e.value == nil ? 0 : 10))}
    static func rowHeight(_ e:Entry,width:CGFloat,left:CGFloat)->CGFloat {
        if e.separator==true{return 12}
        if e.section==true{return 25}
        let titleHeight=height(e.label,font:labelFont(e),width:labelWidth(e,width:width,left:left))
        let detailHeight=e.detail.map{height($0,font:detailFont,width:width-left-trailing(e))+3} ?? 0
        return max(e.actionable ? 27 : 21,titleHeight+detailHeight+(e.detail == nil ? 8 : 12))
    }
    static func flyoutWidth(_ entry:Entry)->CGFloat {
        let left=column(entry.children)
        var needed=width(entry.label,font:.systemFont(ofSize:11,weight:.medium))+left+28
        for e in entry.children where e.separator != true {
            let title=width(e.label,font:labelFont(e))+valueWidth(e)+(e.value == nil ? 0 : 10)
            let detail=e.detail.map{min(216,width($0,font:detailFont))} ?? 0
            needed=max(needed,max(title,detail)+left+trailing(e)+16)
        }
        return min(296,max(224,ceil(needed/8)*8))
    }
    static func draw(_ value:String,in rect:NSRect,font:NSFont,color:NSColor,alignment:NSTextAlignment = .left){
        let style=NSMutableParagraphStyle();style.alignment=alignment;style.lineBreakMode = .byWordWrapping
        (value as NSString).draw(in:rect,withAttributes:[.font:font,.foregroundColor:color,.paragraphStyle:style])
    }
}

final class Row:NSButton {
    let entry:Entry;var invoke:((Entry,Row)->Void)?;var hover:((Entry,Row)->Void)?
    var expanded=false {didSet{needsDisplay=true}}
    var columnInset:CGFloat=12
    private var hovering=false;private var tracking:NSTrackingArea?;private var glyph:NSImage?
    init(_ entry:Entry,frame:NSRect){
        self.entry=entry;super.init(frame:frame);title=entry.label;isBordered=false;setButtonType(.momentaryChange)
        target=self;action=#selector(activate);isEnabled=entry.actionable
        setAccessibilityLabel(entry.label+(entry.detail.map{", "+$0} ?? ""))
        if let raw=entry.image,let data=Data(base64Encoded:raw),let img=NSImage(data:data){glyph=img;glyph?.isTemplate=entry.template ?? false}
        else if let symbol=entry.symbol{glyph=NSImage(systemSymbolName:symbol,accessibilityDescription:nil)}
    }
    required init?(coder:NSCoder){fatalError()}
    @objc private func activate(){invoke?(entry,self)}
    override func viewDidChangeEffectiveAppearance(){super.viewDidChangeEffectiveAppearance();needsDisplay=true}
    override func updateTrackingAreas(){super.updateTrackingAreas();if let tracking{removeTrackingArea(tracking)};tracking=NSTrackingArea(rect:bounds,options:[.mouseEnteredAndExited,.activeAlways,.inVisibleRect],owner:self,userInfo:nil);addTrackingArea(tracking!)}
    override func mouseEntered(with event:NSEvent){hovering=true;needsDisplay=true;hover?(entry,self)}
    override func mouseExited(with event:NSEvent){hovering=false;needsDisplay=true}
    override func draw(_ dirtyRect:NSRect){
        let pointerInside=window.map{$0.isVisible && $0.convertToScreen(convert(bounds,to:nil)).contains(NSEvent.mouseLocation)} ?? false
        if (pointerInside || expanded) && isEnabled {NSColor.controlAccentColor.withAlphaComponent(dark(self) ? 0.12 : 0.09).setFill();NSBezierPath(roundedRect:bounds,xRadius:7,yRadius:7).fill()}
        let left=columnInset
        if let checked=entry.checked {
            let box=NSRect(x:13,y:(bounds.height-12)/2,width:12,height:12)
            let radio=entry.action?.first=="set-appearance"
            let outline=NSBezierPath(roundedRect:box,xRadius:radio ? 6 : 3,yRadius:radio ? 6 : 3)
            if checked {
                NSColor.controlAccentColor.setFill();outline.fill()
                NSColor.white.setStroke();NSColor.white.setFill()
                if radio {NSBezierPath(ovalIn:box.insetBy(dx:4,dy:4)).fill()}
                else {let tick=NSBezierPath();tick.move(to:NSPoint(x:box.minX+2.5,y:box.midY));tick.line(to:NSPoint(x:box.minX+5,y:box.maxY-3));tick.line(to:NSPoint(x:box.maxX-2.5,y:box.minY+3));tick.lineWidth=1.5;tick.lineCapStyle = .round;tick.lineJoinStyle = .round;tick.stroke()}
            } else {NSColor.secondaryLabelColor.withAlphaComponent(0.5).setStroke();outline.lineWidth=1;outline.stroke()}

        } else if let glyph {
            if glyph.isTemplate {
                let image=NSImage(size:NSSize(width:14,height:14));image.lockFocus();glyph.draw(in:NSRect(x:0,y:0,width:14,height:14));(dark(self) ? NSColor(calibratedWhite:0.9,alpha:1) : NSColor(calibratedWhite:0.18,alpha:1)).setFill();NSRect(x:0,y:0,width:14,height:14).fill(using:.sourceIn);image.unlockFocus();image.draw(in:NSRect(x:12,y:(bounds.height-14)/2,width:14,height:14))
            } else {glyph.draw(in:NSRect(x:12,y:(bounds.height-14)/2,width:14,height:14))}
        }
        let trailing=MenuLayout.trailing(entry),font=MenuLayout.labelFont(entry)
        let color:NSColor=entry.action?.first=="stop" || entry.label.hasPrefix("○") ? .systemRed : (entry.label.hasPrefix("●") ? statusGreen(self) : (entry.actionable ? .labelColor : .secondaryLabelColor))
        let labelWidth=MenuLayout.labelWidth(entry,width:bounds.width,left:left)
        let titleHeight=MenuLayout.height(entry.label,font:font,width:labelWidth)
        let detailHeight=entry.detail.map{MenuLayout.height($0,font:MenuLayout.detailFont,width:bounds.width-left-trailing)} ?? 0
        let blockHeight=titleHeight+(entry.detail == nil ? 0 : detailHeight+3)
        let top=(bounds.height-blockHeight)/2
        MenuLayout.draw(entry.label,in:NSRect(x:left,y:top,width:labelWidth,height:titleHeight),font:font,color:color)
        if let value=entry.value {
            let valueWidth=MenuLayout.valueWidth(entry)
            let valueRect=NSRect(x:bounds.width-trailing-valueWidth,y:bounds.midY-10,width:valueWidth,height:20)
            let textHeight=MenuLayout.height(value,font:MenuLayout.valueFont,width:valueWidth)
            if entry.attention==true {
                NSColor.controlAccentColor.withAlphaComponent(dark(self) ? 0.22 : 0.10).setFill()
                NSBezierPath(roundedRect:valueRect,xRadius:7,yRadius:7).fill()
                MenuLayout.draw(value,in:NSRect(x:valueRect.minX+8,y:bounds.midY-textHeight/2,width:valueRect.width-16,height:textHeight),font:MenuLayout.valueFont,color:dark(self) ? accent("opencodex",self) : .controlAccentColor,alignment:.center)
            }else{
                MenuLayout.draw(value,in:NSRect(x:valueRect.minX,y:bounds.midY-textHeight/2,width:valueRect.width,height:textHeight),font:MenuLayout.valueFont,color:entry.actionable ? .labelColor : .secondaryLabelColor,alignment:.right)
            }
        }
        if let detail=entry.detail {MenuLayout.draw(detail,in:NSRect(x:left,y:top+titleHeight+3,width:bounds.width-left-trailing,height:detailHeight),font:MenuLayout.detailFont,color:.secondaryLabelColor)}

        if !entry.children.isEmpty{let p=NSBezierPath();p.move(to:NSPoint(x:bounds.width-19,y:bounds.midY-4));p.line(to:NSPoint(x:bounds.width-15,y:bounds.midY));p.line(to:NSPoint(x:bounds.width-19,y:bounds.midY+4));p.lineWidth=1.2;p.lineJoinStyle = .round;p.lineCapStyle = .round;NSColor.labelColor.setStroke();p.stroke()}
    }
}
struct Flyout {var panel:Panel;var key:String;weak var row:Row?}
final class App:NSObject,NSApplicationDelegate,NSMenuDelegate {
    private let panel=Panel(contentRect:.zero,styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
    private var rangePicker:NSPopUpButton?;private var rangeMenuOpen=false;private var managerOnly=false
    private var snapshot:Snapshot?;private var snapshotPath="";private var pluginPath="";private var modified:Date?
    private var anchor:NSPoint = .zero;private var anchorRect:NSRect = .zero;private var scrollOffset:CGFloat=0
    private var timer:Timer?;private var monitors:[Any]=[];private var pendingAction:String?;private var running=false
    private var activePreference:[String]?;private var queuedPreferences:[[String]]=[]
    private var flyouts:[Flyout]=[];private var rows:[[String:Row]]=[];private var hoverTask:DispatchWorkItem?;private var closeTask:DispatchWorkItem?
    private func setup(_ window:Panel){window.backgroundColor = .clear;window.isOpaque=false;window.hasShadow=true;window.level = .popUpMenu;window.hidesOnDeactivate=false;window.isReleasedWhenClosed=false;window.acceptsMouseMovedEvents=true;window.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary,.transient,.ignoresCycle];window.escape={[weak self] in self?.hide()}}
    func applicationDidFinishLaunching(_ notification:Notification){
        let args=CommandLine.arguments
        guard let si=args.firstIndex(of:"--snapshot"),si+1<args.count,let pi=args.firstIndex(of:"--plugin"),pi+1<args.count else{NSApp.terminate(nil);return}
        snapshotPath=args[si+1];pluginPath=args[pi+1];setup(panel);panel.setAccessibilityLabel("AI 用量面板")
        if let monitor=NSEvent.addGlobalMonitorForEvents(matching:[.leftMouseDown,.rightMouseDown],handler:{[weak self] event in
            guard let self else{return}
            // SwiftBar routes right-click and Option-click to its native menu.
            // Only an ordinary left-click on the star retains the panel toggle.
            if event.type == .rightMouseDown || event.modifierFlags.contains(.option) || !self.anchorRect.contains(NSEvent.mouseLocation){self.hide()}
        }){monitors.append(monitor)}
        if let monitor=NSEvent.addGlobalMonitorForEvents(matching:.mouseMoved,handler:{[weak self] _ in self?.checkPointer()}){monitors.append(monitor)}
        if let monitor=NSEvent.addLocalMonitorForEvents(matching:.mouseMoved,handler:{[weak self] event in self?.checkPointer();return event}){monitors.append(monitor)}
        if let monitor=NSEvent.addLocalMonitorForEvents(matching:.rightMouseDown,handler:{[weak self] event in
            guard let self,let window=event.window,(window === self.panel || self.flyouts.contains(where:{$0.panel === window})),let view=window.contentView else{return event}
            self.showModuleMenu(event,in:view);return nil
        }){monitors.append(monitor)}
        NSWorkspace.shared.notificationCenter.addObserver(self,selector:#selector(accessibilityChanged),name:NSWorkspace.accessibilityDisplayOptionsDidChangeNotification,object:nil)
        timer=Timer.scheduledTimer(withTimeInterval:1,repeats:true){[weak self] _ in guard let self else{return};self.checkAction();if self.panel.isVisible{if self.nativeMenuVisible(){self.hide()}else{self.reload()}}}
        NotificationCenter.default.addObserver(self,selector:#selector(rangeTrackingBegan(_:)),name:NSMenu.didBeginTrackingNotification,object:nil)
        NotificationCenter.default.addObserver(self,selector:#selector(rangeTrackingEnded(_:)),name:NSMenu.didEndTrackingNotification,object:nil)
        show()
    }
    @objc private func accessibilityChanged(){if panel.isVisible{reload(force:true)}}
    private func showModuleMenu(_ event:NSEvent,in view:NSView){
        guard !running else{return}
        rangePicker?.menu?.cancelTracking();rangeMenuOpen=false;hoverTask?.cancel();closeTask?.cancel();closeFlyouts(from:0)
        managerOnly=true;scrollOffset=0;layout()
    }
    @objc private func finishModules(){hide()}
    private func requestedMode()->Bool? {
        let request=URL(fileURLWithPath:snapshotPath).deletingLastPathComponent().appendingPathComponent("panel-open.json")
        guard let data=try? Data(contentsOf:request),let value=try? JSONSerialization.jsonObject(with:data) as? [String:Any],let created=value["createdAt"] as? Double,Date().timeIntervalSince1970-created<30 else{return nil}
        try? FileManager.default.removeItem(at:request)
        return value["mode"] as? String=="modules"
    }
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool{let requested=requestedMode();if panel.isVisible && (requested == nil || requested==managerOnly){hide()}else{if let requested{managerOnly=requested};show()};return false}
    private func nativeMenuVisible()->Bool {
        let windows=CGWindowListCopyWindowInfo([.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID) as? [[String:Any]] ?? []
        return windows.contains {row in
            guard row[kCGWindowOwnerName as String] as? String == "SwiftBar",
                  let layer=row[kCGWindowLayer as String] as? Int,layer==NSWindow.Level.popUpMenu.rawValue,
                  let bounds=row[kCGWindowBounds as String] as? [String:Double] else{return false}
            return (bounds["Width"] ?? 0)>80 && (bounds["Height"] ?? 0)>30
        }
    }
    private func show(){if let requested=requestedMode(){managerOnly=requested};guard !nativeMenuVisible() else{hide();return};scrollOffset=0;anchor=NSEvent.mouseLocation;let screen=NSScreen.screens.first(where:{$0.frame.contains(anchor)}) ?? NSScreen.main!;anchorRect=NSRect(x:anchor.x-24,y:screen.visibleFrame.maxY,width:48,height:screen.frame.maxY-screen.visibleFrame.maxY+8);reload(force:true);panel.makeKeyAndOrderFront(nil)}
    private func hide(){rangePicker?.menu?.cancelTracking();hoverTask?.cancel();closeTask?.cancel();closeFlyouts(from:0);panel.orderOut(nil)}
    private func reload(force:Bool=false){guard !rangeMenuOpen else{return};let date=(try? FileManager.default.attributesOfItem(atPath:snapshotPath)[.modificationDate]) as? Date;guard force || date != modified else{return};guard let data=try? Data(contentsOf:URL(fileURLWithPath:snapshotPath)),let value=try? JSONDecoder().decode(Snapshot.self,from:data) else{return};modified=date;var current=value;if let activePreference{applyPreference(activePreference,to:&current)};for queued in queuedPreferences{applyPreference(queued,to:&current)};snapshot=current;layout()}
    private func fillRows(_ entries:[Entry],in content:NSView,y start:CGFloat,width:CGFloat,depth:Int)->CGFloat {
        while rows.count<=depth{rows.append([:])};rows[depth]=[:];var y=start
        for original in entries {var entry=original;if running,let name=entry.action?.first,["refresh","refresh-monitor","check-app-updates","set-range"].contains(name){entry.label="正在刷新…"}
            let left=MenuLayout.column(entries),h=MenuLayout.rowHeight(entry,width:width,left:left)
            if entry.separator==true {let divider=NSBox(frame:NSRect(x:8,y:y+5,width:width-16,height:1));divider.boxType = .separator;content.addSubview(divider)}
            else {let row=Row(entry,frame:NSRect(x:0,y:y,width:width,height:h));row.columnInset=entry.section==true ? 12 : left;row.invoke={[weak self] e,r in self?.activate(e,row:r,depth:depth)};row.hover={[weak self] e,r in self?.hover(e,row:r,depth:depth)};content.addSubview(row);rows[depth][entry.key]=row}
            y+=h
        };return y
    }
    private func layout(){
        guard !rangeMenuOpen,let snapshot else{return};if panel.isVisible,let old=(panel.contentView as? Surface)?.content.subviews.first as? NSScrollView {scrollOffset=old.contentView.bounds.origin.y};let opened=flyouts.map{$0.key};closeFlyouts(from:0);rows=[]
        let screen=NSScreen.screens.first(where:{$0.frame.contains(anchor)}) ?? NSScreen.main!,width:CGFloat=managerOnly ? 280 : 360,inner=width-16
        let entries=managerOnly ? snapshot.moduleOptions ?? [] : snapshot.entries
        let top:CGFloat=managerOnly ? 49 : (snapshot.dashboard.map{DashboardView.height($0)+8} ?? 36)
        let body=entries.reduce(CGFloat(0)){$0+MenuLayout.rowHeight($1,width:inner,left:MenuLayout.column(entries))},contentHeight=top+body
        let height=min(contentHeight+16,screen.visibleFrame.height-16)
        let surface=Surface(frame:NSRect(x:0,y:0,width:width,height:height),glass:self.snapshot?.appearance != "solid")
        let scroll=NSScrollView(frame:NSRect(x:8,y:8,width:inner,height:height-16));scroll.drawsBackground=false;scroll.hasVerticalScroller=contentHeight>scroll.frame.height;scroll.scrollerStyle = .overlay
        let content=FlippedView(frame:NSRect(x:0,y:0,width:inner,height:contentHeight))
        if managerOnly {
            let heading=NSTextField(labelWithString:"主页模块");heading.font = .systemFont(ofSize:14,weight:.semibold);heading.frame=NSRect(x:12,y:7,width:inner-85,height:20);content.addSubview(heading)
            let count=entries.filter{$0.action?.first=="set-module" && $0.checked==true}.count
            let hint=NSTextField(labelWithString:"已启用 \(count) 项 · 可连续选择");hint.font = .systemFont(ofSize:10);hint.textColor = .secondaryLabelColor;hint.frame=NSRect(x:12,y:29,width:inner-24,height:15);content.addSubview(hint)
            let done=NSButton(title:"完成",target:self,action:#selector(finishModules));done.bezelStyle = .rounded;done.controlSize = .small;done.frame=NSRect(x:inner-65,y:8,width:53,height:25);content.addSubview(done)
        } else if let dashboard=snapshot.dashboard{let view=DashboardView(dashboard,width:inner);content.addSubview(view)}else{let label=NSTextField(labelWithString:"AI 用量面板");label.frame=NSRect(x:12,y:10,width:300,height:20);content.addSubview(label)}
        let divider=NSBox(frame:NSRect(x:8,y:top-5,width:inner-16,height:1));divider.boxType = .separator;content.addSubview(divider)
        _=fillRows(entries,in:content,y:top,width:inner,depth:0)
        if !managerOnly,let dashboard=snapshot.dashboard,let choices=snapshot.rangeOptions {
            let picker=NSPopUpButton(frame:NSRect(x:inner-113,y:7.5,width:101,height:25),pullsDown:true)
            picker.controlSize = .small;picker.font = .systemFont(ofSize:11);picker.bezelStyle = .rounded
            picker.preferredEdge = .maxY;picker.setAccessibilityLabel("统计范围 · "+dashboard.rangeLabel)
            let menu=NSMenu(title:"统计范围");menu.autoenablesItems=false;menu.delegate=self
            let title=NSMenuItem(title:dashboard.rangeLabel,action:nil,keyEquivalent:"");menu.addItem(title)
            for choice in choices {
                let option=NSMenuItem(title:choice.label,action:#selector(chooseRange(_:)),keyEquivalent:"")
                option.target=self;option.representedObject=choice.action;option.state=choice.checked==true ? .on : .off
                option.isEnabled = !running;menu.addItem(option)
            }
            picker.menu=menu;menu.delegate=self;rangePicker=picker;content.addSubview(picker)
        }
        scroll.documentView=content;scroll.contentView.scroll(to:NSPoint(x:0,y:min(scrollOffset,max(0,contentHeight-scroll.frame.height))));surface.content.addSubview(scroll);panel.contentView=surface
        let x=min(max(anchor.x-22,screen.visibleFrame.minX+4),screen.visibleFrame.maxX-width-4)
        panel.setFrame(NSRect(x:x,y:screen.visibleFrame.maxY-height-4,width:width,height:height),display:true)
        for (depth,key) in opened.enumerated(){guard rows.indices.contains(depth),let row=rows[depth][key] else{break};openFlyout(row.entry,row:row,depth:depth)}
        DispatchQueue.main.async{[weak self] in self?.checkPointer()}
    }
    private func rowRect(_ row:Row)->NSRect{guard let window=row.window else{return .zero};return window.convertToScreen(row.convert(row.bounds,to:nil))}
    private func hover(_ entry:Entry,row:Row,depth:Int){
        guard !rangeMenuOpen else{return}
        closeTask?.cancel();hoverTask?.cancel()
        let task=DispatchWorkItem{[weak self,weak row] in guard let self,let row,self.rowRect(row).contains(NSEvent.mouseLocation) else{return};if entry.children.isEmpty{self.closeFlyouts(from:depth)}else{self.openFlyout(entry,row:row,depth:depth)}}
        hoverTask=task;DispatchQueue.main.asyncAfter(deadline:.now()+0.08,execute:task)
    }
    private func openFlyout(_ entry:Entry,row:Row,depth:Int){
        guard !entry.children.isEmpty,let parent=row.window else{return}
        if flyouts.indices.contains(depth),flyouts[depth].key==entry.key{return}
        closeFlyouts(from:depth);row.expanded=true
        let window=Panel(contentRect:.zero,styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false);setup(window);window.setAccessibilityLabel(entry.label)
        let screen=parent.screen ?? NSScreen.main!,width=MenuLayout.flyoutWidth(entry),body=entry.children.reduce(CGFloat(0)){$0+MenuLayout.rowHeight($1,width:MenuLayout.flyoutWidth(entry)-16,left:MenuLayout.column(entry.children))}
        let height=min(body+40,screen.visibleFrame.height-16),surface=Surface(frame:NSRect(x:0,y:0,width:width,height:height),glass:self.snapshot?.appearance != "solid")
        let heading=NSTextField(labelWithString:entry.label);heading.font = .systemFont(ofSize:11,weight:.medium);heading.textColor = .secondaryLabelColor;let headingLeft=MenuLayout.column(entry.children)+8;heading.frame=NSRect(x:headingLeft,y:10,width:width-headingLeft-20,height:18);surface.content.addSubview(heading)
        let scroll=NSScrollView(frame:NSRect(x:8,y:32,width:width-16,height:height-40));scroll.drawsBackground=false;scroll.hasVerticalScroller=body>scroll.frame.height;scroll.scrollerStyle = .overlay
        let content=FlippedView(frame:NSRect(x:0,y:0,width:width-16,height:body));_=fillRows(entry.children,in:content,y:0,width:width-16,depth:depth+1);scroll.documentView=content;surface.content.addSubview(scroll);window.contentView=surface
        var x=parent.frame.maxX+5;if x+width>screen.visibleFrame.maxX-4{x=parent.frame.minX-width-5}
        x=max(screen.visibleFrame.minX+4,min(x,screen.visibleFrame.maxX-width-4))
        let rect=rowRect(row),y=max(screen.visibleFrame.minY+4,min(rect.maxY+6-height,screen.visibleFrame.maxY-height-4))
        window.setFrame(NSRect(x:x,y:y,width:width,height:height),display:true);parent.addChildWindow(window,ordered:.above);window.orderFront(nil);flyouts.append(Flyout(panel:window,key:entry.key,row:row))
    }
    private func closeFlyouts(from depth:Int){
        guard depth<flyouts.count else{return}
        for flyout in flyouts[depth...].reversed(){flyout.row?.expanded=false;flyout.panel.parent?.removeChildWindow(flyout.panel);flyout.panel.orderOut(nil)}
        flyouts.removeSubrange(depth...);if rows.count>depth+1{rows.removeSubrange((depth+1)...)}
    }
    private func checkPointer(){
        guard panel.isVisible,!rangeMenuOpen else{return}
        let p=NSEvent.mouseLocation
        for group in rows{for row in group.values{row.needsDisplay=true}}
        for depth in rows.indices.reversed(){
            if let row=rows[depth].values.first(where:{rowRect($0).contains(p)}) {
                closeTask?.cancel()
                if row.entry.children.isEmpty {
                    if flyouts.count>depth{hover(row.entry,row:row,depth:depth)}
                }else if !flyouts.indices.contains(depth) || flyouts[depth].key != row.entry.key {
                    hover(row.entry,row:row,depth:depth)
                }
                return
            }
        }
        guard !flyouts.isEmpty else{return}
        if flyouts.contains(where:{$0.panel.frame.contains(p)}){closeTask?.cancel();return}
        if closeTask==nil || closeTask!.isCancelled {
            let task=DispatchWorkItem{[weak self] in self?.closeFlyouts(from:0);self?.closeTask=nil}
            closeTask=task;DispatchQueue.main.asyncAfter(deadline:.now()+0.18,execute:task)
        }
    }
    private func applyPreference(_ action:[String],to value:inout Snapshot){
        guard let kind=action.first else{return}
        if kind=="set-module",action.count==3 {
            for i in value.moduleOptions?.indices ?? 0..<0 where value.moduleOptions?[i].action?.prefix(2).elementsEqual(action.prefix(2)) == true {
                let enabled=action[2]=="true";value.moduleOptions?[i].checked=enabled
                value.moduleOptions?[i].action=["set-module",action[1],enabled ? "false" : "true"]
            }
        }
        if kind=="set-appearance",action.count==2 {
            value.appearance=action[1]
            func update(_ entries:inout [Entry]){
                for i in entries.indices {
                    if entries[i].action?.first=="set-appearance" {entries[i].checked=entries[i].action?.last==action[1]}
                    update(&entries[i].children)
                }
            }
            if var entries=value.moduleOptions{update(&entries);value.moduleOptions=entries}
        }
    }

    private func checkAction(){
        guard let pendingAction else{return}
        let receipt=URL(fileURLWithPath:snapshotPath).deletingLastPathComponent().appendingPathComponent("panel-action-receipt.json")
        guard let data=try? Data(contentsOf:receipt),let value=try? JSONSerialization.jsonObject(with:data) as? [String:Any],value["id"] as? String==pendingAction else{return}
        self.pendingAction=nil;activePreference=nil;running=false
        if value["status"] as? String != "done" {
            queuedPreferences=[];reload(force:true)
            let alert=NSAlert();alert.messageText="操作未完成";alert.informativeText="请重新打开菜单后重试。";alert.addButton(withTitle:"好");alert.runModal();return
        }
        reload(force:true)
        if !queuedPreferences.isEmpty {let next=queuedPreferences.removeFirst();performAction(next)}
    }
    private func activate(_ entry:Entry,row:Row,depth:Int){
        if !entry.children.isEmpty{openFlyout(entry,row:row,depth:depth);return}
        if let href=entry.href,let url=URL(string:href),["http","https","swiftbar"].contains(url.scheme ?? ""){hide();NSWorkspace.shared.open(url);return}
        if let action=entry.action{performAction(action)}
    }
    @objc private func rangeTrackingBegan(_ notification:Notification){if let menu=notification.object as? NSMenu,menu === rangePicker?.menu{menuWillOpen(menu)}}
    @objc private func rangeTrackingEnded(_ notification:Notification){if let menu=notification.object as? NSMenu,menu === rangePicker?.menu{menuDidClose(menu)}}
    func menuWillOpen(_ menu:NSMenu){rangeMenuOpen=true;hoverTask?.cancel();closeTask?.cancel();closeFlyouts(from:0)}
    func menuDidClose(_ menu:NSMenu){rangeMenuOpen=false;DispatchQueue.main.async{[weak self] in self?.reload(force:true)}}
    @objc private func chooseRange(_ item:NSMenuItem){if let action=item.representedObject as? [String]{performAction(action)}}
    private func abortAction(){
        pendingAction=nil;activePreference=nil;queuedPreferences=[];running=false
        try? FileManager.default.removeItem(at:URL(fileURLWithPath:snapshotPath).deletingLastPathComponent().appendingPathComponent("panel-action.json"))
        reload(force:true);NSSound.beep()
    }
    private func performAction(_ action:[String]){
        guard !action.isEmpty else{return}
        let preference=["set-module","set-appearance","reset-modules"].contains(action[0])
        if running {
            if preference,queuedPreferences.count<64 {queuedPreferences.append(action);if var value=snapshot{applyPreference(action,to:&value);snapshot=value};layout()}
            return
        }
        if preference {activePreference=action;if var value=snapshot{applyPreference(action,to:&value);snapshot=value}}
        let keepOpen=["refresh","refresh-monitor","check-app-updates","set-range","set-module","set-appearance","reset-modules"].contains(action[0]);if !keepOpen{hide()};running=true;if keepOpen{layout()}
        let id=UUID().uuidString,request=URL(fileURLWithPath:snapshotPath).deletingLastPathComponent().appendingPathComponent("panel-action.json")
        do{let data=try JSONSerialization.data(withJSONObject:["id":id,"action":action,"createdAt":Date().timeIntervalSince1970]);try data.write(to:request,options:.atomic);try FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:request.path);pendingAction=id
            var url=URLComponents();url.scheme="swiftbar";url.host="refreshplugin";url.queryItems=[URLQueryItem(name:"name",value:URL(fileURLWithPath:pluginPath).lastPathComponent)]
            if !NSWorkspace.shared.open(url.url!){abortAction()}
        }catch{abortAction()}
    }
}
UserDefaults.standard.setVolatileDomain(["AppleAccentColor":4,"AppleAquaColorVariant":1],forName:UserDefaults.argumentDomain)
let app=NSApplication.shared;app.setActivationPolicy(.accessory);let delegate=App();app.delegate=delegate;app.run()
