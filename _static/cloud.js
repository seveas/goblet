/* ~~~~~~~~~~~~~~
 * cloud.js_t
 * ~~~~~~~~~~~~~~
 *
 * Various bits of javascript driving the moving parts behind various
 * parts of the cloud theme. Handles things such as toggleable sections,
 * collapsing the sidebar, etc.
 *
 * :copyright: Copyright 2011-2012 by Assurance Technologies
 * :license: BSD
 */

/* ==========================================================================
 * highlighter #2
 * ==========================================================================
 *
 * Sphinx's highlighter marks some objects when user follows link,
 * but doesn't include section names, etc. This catches those.
 */
$(document).ready(function (){
  // helper to locate highlight target based on #fragment
  function locate_target(){
    // find id referenced by #fragment
    var hash = document.location.hash;
    if(!hash) return null;
    var section = document.getElementById(hash.substr(1));
    if(!section) return null;

    // could be div.section, or hidden span at top of div.section
    var name = section.nodeName.toLowerCase();
    if(name != "div"){
      if(name == "span" && section.innerHTML == "" &&
         section.parentNode.nodeName.toLowerCase() == "div"){
        section = section.parentNode;
      }
    }
    // now at section div and either way we have to find title element - h2, h3, etc.
    var children = $(section).children("h2, h3, h4, h5, h6");
    return children.length ? children : null;
  }

  // init highlight
  var target = locate_target();
  if(target) target.addClass("highlighted");

  // update highlight if hash changes
  $(window).bind("hashchange", function () {
    if(target) target.removeClass("highlighted");
    target = locate_target();
    if(target) target.addClass("highlighted");
  });
});

/* ==========================================================================
 * toggleable sections
 * ==========================================================================
 *
 * Added expand/collapse button to any collapsible RST sections.
 * Looks for sections with CSS class "html-toggle",
 * along with the optional classes "expanded" or "collapsed".
 * Button toggles "html-toggle.expanded/collapsed" classes,
 * and relies on CSS to do the rest of the job displaying them as appropriate.
 */

$(document).ready(function (){
  function init(){
    // get header & section, and add static classes
    var header = $(this);
    var section = header.parent();
    header.addClass("html-toggle-button");

    // helper to test if url hash is within this section
    function contains_hash(){
      var hash = document.location.hash;
      return hash && (section[0].id == hash.substr(1) ||
              section.find(hash.replace(/\./g,"\\.")).length>0);
    }

    // helper to control toggle state
    function set_state(expanded){
      if(expanded){
        section.addClass("expanded").removeClass("collapsed");
        section.children().show();
      }else{
        section.addClass("collapsed").removeClass("expanded");
        section.children().hide();
        section.children("span:first-child:empty").show(); /* for :ref: span tag */
        header.show();
      }
    }

    // initialize state
    set_state(section.hasClass("expanded") || contains_hash());

    // bind toggle callback
    header.click(function (){
      set_state(!section.hasClass("expanded"));
      $(window).trigger('cloud-section-toggled', section[0]);
    });

    // open section if user jumps to it from w/in page
    $(window).bind("hashchange", function () {
      if(contains_hash()) set_state(true);
    });
  }

  $(".html-toggle.section > h2, .html-toggle.section > h3, .html-toggle.section > h4, .html-toggle.section > h5, .html-toggle.section > h6").each(init);
});
/* ==========================================================================
 * collapsible sidebar
 * ==========================================================================
 *
 * Adds button for collapsing & expanding sidebar,
 * which toggles "document.collapsed-sidebar" CSS class,
 * and relies on CSS for actual styling of visible & hidden sidebars.
 */

$(document).ready(function (){
  var holder = $('<div class="sidebartoggle"><button id="sidebar-hide" title="click to hide the sidebar">&laquo;</button><button id="sidebar-show" style="display: none" title="click to show the sidebar">sidebar &raquo;</button></div>');
  var doc = $('div.document');

  var show_btn = $('#sidebar-show', holder);
  var hide_btn = $('#sidebar-hide', holder);
  var copts = { expires: 7, path: DOCUMENTATION_OPTIONS.url_root };

  show_btn.click(function (){
    doc.removeClass("collapsed-sidebar");
    hide_btn.show();
    show_btn.hide();
    $.cookie("sidebar", "expanded", copts);
    $(window).trigger("cloud-sidebar-toggled", false);
  });

  hide_btn.click(function (){
    doc.addClass("collapsed-sidebar");
    show_btn.show();
    hide_btn.hide();
    $.cookie("sidebar", "collapsed", copts);
    $(window).trigger("cloud-sidebar-toggled", true);
  });

  var state = $.cookie("sidebar");


  doc.append(holder);

  if (state == "collapsed"){
    doc.addClass("collapsed-sidebar");
    show_btn.show();
    hide_btn.hide();
  }
});

/* ==========================================================================
 * header breaker
 * ==========================================================================
 *
 * attempts to intelligently insert linebreaks into page titles, where possible.
 * currently only handles titles such as "module - description",
 * adding a break after the "-".
 */
$(document).ready(function (){
  // get header's content, insert linebreaks
  var header = $("h1");
  var orig = header[0].innerHTML;
  var shorter = orig;
  if($("h1 > a:first > tt > span.pre").length > 0){
      shorter = orig.replace(/(<\/tt><\/a>\s*[-\u2013\u2014:]\s+)/im, "$1<br> ");
  }
  else if($("h1 > tt.literal:first").length > 0){
      shorter = orig.replace(/(<\/tt>\s*[-\u2013\u2014:]\s+)/im, "$1<br> ");
  }
  if(shorter == orig){
    return;
  }

  // hack to determine full width of header
  header.css({whiteSpace: "nowrap", position:"absolute"});
  var header_width = header.width();
  header.css({whiteSpace: "", position: ""});

  // func to insert linebreaks when needed
  function layout_header(){
    header[0].innerHTML = (header_width > header.parent().width()) ? shorter : orig;
  }

  // run function now, and every time window is resized
  layout_header();
  $(window).resize(layout_header)
           .bind('cloud-sidebar-toggled', layout_header);
});