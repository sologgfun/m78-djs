import{i as S,b as j,d as m,c as D}from"./index-evTTxdcx.js";import{B,s as C,f as N,o as b,c as x,m as P,r as U,b as T,H as I,e as t,a,z as r,M as d,t as s,y as v,P as f,p as h}from"./index-CzHWZgh2.js";import{s as _}from"./index-Can2bZ8B.js";var E=`
    .p-divider-horizontal {
        display: flex;
        width: 100%;
        position: relative;
        align-items: center;
        margin: dt('divider.horizontal.margin');
        padding: dt('divider.horizontal.padding');
    }

    .p-divider-horizontal:before {
        position: absolute;
        display: block;
        inset-block-start: 50%;
        inset-inline-start: 0;
        width: 100%;
        content: '';
        border-block-start: 1px solid dt('divider.border.color');
    }

    .p-divider-horizontal .p-divider-content {
        padding: dt('divider.horizontal.content.padding');
    }

    .p-divider-vertical {
        min-height: 100%;
        display: flex;
        position: relative;
        justify-content: center;
        margin: dt('divider.vertical.margin');
        padding: dt('divider.vertical.padding');
    }

    .p-divider-vertical:before {
        position: absolute;
        display: block;
        inset-block-start: 0;
        inset-inline-start: 50%;
        height: 100%;
        content: '';
        border-inline-start: 1px solid dt('divider.border.color');
    }

    .p-divider.p-divider-vertical .p-divider-content {
        padding: dt('divider.vertical.content.padding');
    }

    .p-divider-content {
        z-index: 1;
        background: dt('divider.content.background');
        color: dt('divider.content.color');
    }

    .p-divider-solid.p-divider-horizontal:before {
        border-block-start-style: solid;
    }

    .p-divider-solid.p-divider-vertical:before {
        border-inline-start-style: solid;
    }

    .p-divider-dashed.p-divider-horizontal:before {
        border-block-start-style: dashed;
    }

    .p-divider-dashed.p-divider-vertical:before {
        border-inline-start-style: dashed;
    }

    .p-divider-dotted.p-divider-horizontal:before {
        border-block-start-style: dotted;
    }

    .p-divider-dotted.p-divider-vertical:before {
        border-inline-start-style: dotted;
    }

    .p-divider-left:dir(rtl),
    .p-divider-right:dir(rtl) {
        flex-direction: row-reverse;
    }
`,R={root:function(n){var i=n.props;return{justifyContent:i.layout==="horizontal"?i.align==="center"||i.align===null?"center":i.align==="left"?"flex-start":i.align==="right"?"flex-end":null:null,alignItems:i.layout==="vertical"?i.align==="center"||i.align===null?"center":i.align==="top"?"flex-start":i.align==="bottom"?"flex-end":null:null}}},H={root:function(n){var i=n.props;return["p-divider p-component","p-divider-"+i.layout,"p-divider-"+i.type,{"p-divider-left":i.layout==="horizontal"&&(!i.align||i.align==="left")},{"p-divider-center":i.layout==="horizontal"&&i.align==="center"},{"p-divider-right":i.layout==="horizontal"&&i.align==="right"},{"p-divider-top":i.layout==="vertical"&&i.align==="top"},{"p-divider-center":i.layout==="vertical"&&(!i.align||i.align==="center")},{"p-divider-bottom":i.layout==="vertical"&&i.align==="bottom"}]},content:"p-divider-content"},K=B.extend({name:"divider",style:E,classes:H,inlineStyles:R}),L={name:"BaseDivider",extends:C,props:{align:{type:String,default:null},layout:{type:String,default:"horizontal"},type:{type:String,default:"solid"}},style:K,provide:function(){return{$pcDivider:this,$parentInstance:this}}};function y(o){"@babel/helpers - typeof";return y=typeof Symbol=="function"&&typeof Symbol.iterator=="symbol"?function(n){return typeof n}:function(n){return n&&typeof Symbol=="function"&&n.constructor===Symbol&&n!==Symbol.prototype?"symbol":typeof n},y(o)}function w(o,n,i){return(n=O(n))in o?Object.defineProperty(o,n,{value:i,enumerable:!0,configurable:!0,writable:!0}):o[n]=i,o}function O(o){var n=q(o,"string");return y(n)=="symbol"?n:n+""}function q(o,n){if(y(o)!="object"||!o)return o;var i=o[Symbol.toPrimitive];if(i!==void 0){var c=i.call(o,n);if(y(c)!="object")return c;throw new TypeError("@@toPrimitive must return a primitive value.")}return(n==="string"?String:Number)(o)}var V={name:"Divider",extends:L,inheritAttrs:!1,computed:{dataP:function(){return N(w(w(w({},this.align,this.align),this.layout,this.layout),this.type,this.type))}}},G=["aria-orientation","data-p"],J=["data-p"];function Q(o,n,i,c,u,p){return b(),x("div",P({class:o.cx("root"),style:o.sx("root"),role:"separator","aria-orientation":o.layout,"data-p":p.dataP},o.ptmi("root")),[o.$slots.default?(b(),x("div",P({key:0,class:o.cx("content"),"data-p":p.dataP},o.ptm("content")),[U(o.$slots,"default")],16,J)):T("",!0)],16,G)}V.render=Q;const W={class:"view-container",style:{height:"calc(100vh - 80px)",overflow:"hidden",padding:"1rem"}},X={class:"grid h-full",style:{margin:"0","align-items":"stretch"}},Y={class:"col-12 lg:col-4 h-full"},Z={class:"gh-card h-full flex flex-column overflow-hidden"},tt={class:"gh-card-body flex-1 overflow-auto"},et={class:"flex flex-column gap-4 p-3"},it={class:"flex flex-column gap-2 mb-1"},ot={class:"flex flex-column gap-2"},nt={class:"flex flex-column gap-3"},lt={class:"param-item"},st={class:"flex justify-content-between mb-2"},rt={class:"text-primary font-bold"},dt={class:"param-item"},at={class:"flex justify-content-between mb-2"},ct={class:"text-primary font-bold"},pt={class:"param-item"},ut={class:"flex justify-content-between mb-2"},vt={class:"text-primary font-bold"},ft={class:"col-12 lg:col-8 h-full"},mt={class:"gh-card h-full flex flex-column overflow-hidden"},bt={class:"gh-card-body flex-1 overflow-auto"},xt={class:"p-3"},yt={class:"grid mb-4"},gt={class:"col-12 md:col-4"},ht={class:"surface-card p-3 border-1 border-200 border-round"},_t={class:"text-xl font-bold text-primary"},wt={class:"text-xs text-400"},St={class:"col-12 md:col-4"},Pt={class:"surface-card p-3 border-1 border-200 border-round"},Vt={class:"text-xl font-bold text-green-600"},kt={class:"text-xs text-400"},zt={class:"col-12 md:col-4"},$t={class:"surface-card p-3 border-1 border-200 border-round"},At={class:"text-xl font-bold text-orange-600"},Ft={class:"text-xs text-400"},Mt={class:"font-bold text-primary"},jt={key:0,class:"text-green-600 font-bold"},Dt={key:1,class:"text-400 italic"},Bt={class:"mt-4 p-3 surface-50 border-round text-xs text-600 border-left-3 border-primary"},Ct={class:"m-0"},Nt={__name:"SimulatorView",setup(o){const n=f(100),i=f(88),c=f(88),u=f(12),p=f(112),k=f([{ratio:.88,fund:.1},{ratio:.8,fund:.2},{ratio:.72,fund:.3},{ratio:.64,fund:.4}]),z=h(()=>(n.value*(c.value/100)).toFixed(2)),$=h(()=>(n.value*(p.value/100)).toFixed(2)),A=h(()=>(i.value*(1+u.value/100)).toFixed(2)),F=h(()=>k.value.map((g,e)=>{const l=(n.value*g.ratio).toFixed(2),M=(i.value*(1+u.value/100)).toFixed(2);return{index:e,ratio:g.ratio,fund:g.fund,buyPrice:l,targetSell:e===0?M:"跟随购买价计算"}}));return(g,e)=>(b(),x("div",W,[t("div",X,[t("div",Y,[t("div",Z,[e[13]||(e[13]=t("div",{class:"gh-card-header shrink-0"},[t("i",{class:"pi pi-sliders-h mr-2"}),a("模拟参数输入 ")],-1)),t("div",tt,[t("div",et,[t("div",it,[e[5]||(e[5]=t("label",{class:"font-bold text-sm flex align-items-center"},[t("i",{class:"pi pi-chart-line mr-2 text-primary"}),a("120日均线价格 (MA120) ")],-1)),r(d(S),{modelValue:n.value,"onUpdate:modelValue":e[0]||(e[0]=l=>n.value=l),mode:"decimal",minFractionDigits:2,class:"w-full",inputClass:"py-2 px-3 font-mono",prefix:"¥ "},null,8,["modelValue"]),e[6]||(e[6]=t("small",{class:"text-400"},"行情软件中的 120 日移动平均价",-1))]),t("div",ot,[e[7]||(e[7]=t("label",{class:"font-bold text-sm flex align-items-center"},[t("i",{class:"pi pi-shopping-cart mr-2 text-green-600"}),a("实际买入价格 ")],-1)),r(d(S),{modelValue:i.value,"onUpdate:modelValue":e[1]||(e[1]=l=>i.value=l),mode:"decimal",minFractionDigits:2,class:"w-full",inputClass:"py-2 px-3 font-mono",prefix:"¥ "},null,8,["modelValue"]),e[8]||(e[8]=t("small",{class:"text-400"},"您在账户中的实际成交均价",-1))]),r(d(V),{class:"my-2"}),t("div",nt,[e[12]||(e[12]=t("label",{class:"font-bold text-sm text-primary flex align-items-center"},[t("i",{class:"pi pi-cog mr-2"}),a("策略核心参数 ")],-1)),t("div",lt,[t("div",st,[e[9]||(e[9]=t("span",{class:"text-xs font-semibold"},[a("入场信号 "),t("span",{class:"text-400 font-normal ml-1"},"价格 ≤ MA120 ×")],-1)),t("span",rt,s(c.value)+"%",1)]),r(d(_),{modelValue:c.value,"onUpdate:modelValue":e[2]||(e[2]=l=>c.value=l),min:50,max:100},null,8,["modelValue"])]),t("div",dt,[t("div",at,[e[10]||(e[10]=t("span",{class:"text-xs font-semibold"},[a("单层止盈 "),t("span",{class:"text-400 font-normal ml-1"},"目标收益比")],-1)),t("span",ct,s(u.value)+"%",1)]),r(d(_),{modelValue:u.value,"onUpdate:modelValue":e[3]||(e[3]=l=>u.value=l),min:1,max:50},null,8,["modelValue"])]),t("div",pt,[t("div",ut,[e[11]||(e[11]=t("span",{class:"text-xs font-semibold"},[a("全仓清仓 "),t("span",{class:"text-400 font-normal ml-1"},"价格 ≥ MA120 ×")],-1)),t("span",vt,s(p.value)+"%",1)]),r(d(_),{modelValue:p.value,"onUpdate:modelValue":e[4]||(e[4]=l=>p.value=l),min:100,max:150},null,8,["modelValue"])])])])])])]),t("div",ft,[t("div",mt,[e[21]||(e[21]=t("div",{class:"gh-card-header shrink-0"},[t("i",{class:"pi pi-bolt mr-2 text-warning"}),a("量化价位建议 ")],-1)),t("div",bt,[t("div",xt,[t("div",yt,[t("div",gt,[t("div",ht,[e[14]||(e[14]=t("div",{class:"text-500 text-xs mb-1"},"建议入场价",-1)),t("div",_t,"¥"+s(z.value),1),t("div",wt,"MA120 * "+s(c.value)+"%",1)])]),t("div",St,[t("div",Pt,[e[15]||(e[15]=t("div",{class:"text-500 text-xs mb-1"},"首层止盈价",-1)),t("div",Vt,"¥"+s(A.value),1),t("div",kt,"买入价 * (1 + "+s(u.value)+"%)",1)])]),t("div",zt,[t("div",$t,[e[16]||(e[16]=t("div",{class:"text-500 text-xs mb-1"},"全仓清仓价",-1)),t("div",At,"¥"+s($.value),1),t("div",Ft,"MA120 * "+s(p.value)+"%",1)])])]),e[20]||(e[20]=t("div",{class:"font-bold mb-3 text-800"},"补仓梯级表 (向下金字塔)",-1)),r(d(j),{value:F.value,size:"small",stripedRows:"",class:"border-1 border-200 border-round overflow-hidden"},{default:v(()=>[r(d(m),{field:"index",header:"层级"},{body:v(({data:l})=>[r(d(D),{value:"L"+l.index,severity:l.index===0?"info":"warning"},null,8,["value","severity"])]),_:1}),r(d(m),{field:"ratio",header:"MA120比例"},{body:v(({data:l})=>[a(s((l.ratio*100).toFixed(0))+"% ",1)]),_:1}),r(d(m),{field:"buyPrice",header:"目标买入价"},{body:v(({data:l})=>[t("span",Mt,"¥"+s(l.buyPrice),1)]),_:1}),r(d(m),{field:"targetSell",header:"止盈价 (该层)"},{body:v(({data:l})=>[l.index===0?(b(),x("span",jt,"¥"+s(l.targetSell),1)):(b(),x("span",Dt,"买入价 * (1+"+s(u.value)+")",1))]),_:1}),r(d(m),{field:"fund",header:"分配权重"},{body:v(({data:l})=>[a(s((l.fund*100).toFixed(0))+"% ",1)]),_:1})]),_:1},8,["value"]),t("div",Bt,[e[17]||(e[17]=t("div",{class:"font-bold mb-1"},"使用说明：",-1)),e[18]||(e[18]=t("p",{class:"m-0"},"1. 输入当天的 MA120 价格，系统会计算理论入场点。",-1)),e[19]||(e[19]=t("p",{class:"m-0"},"2. 输入您的实际买入价，系统会计算对应的补仓位和第一层止盈位。",-1)),t("p",Ct,"3. 当股价回升触及 MA120 * "+s(p.value)+" 时，建议不论盈亏全仓清出。",1)])])])])])])]))}},Et=I(Nt,[["__scopeId","data-v-4a6e6a5d"]]);export{Et as default};
