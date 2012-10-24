function load_tree_log() {
    var logurl = '/j/' + repo + '/treechanged/' + (ref ? ref + '/' : '' ) + (path ? path + '/' : '');
    $.getJSON(logurl, success=function(data) {
        $.each(data, function(key, val) {
            $('#age_' + val[0]).html(val[1]);
            $('#msg_' + val[0]).html('<a href="/' + repo + '/commit/' +  val[2] + '/">' + val[3] + '</a>');
        });
    });
}
function toggle_longlog() {
    $(this).parent().children('pre').toggleClass('invisible');
}
function switch_branch() {
    var branch = $(this).attr('value');
    if($.inArray(action, ['commits', 'commit'])>=0) {
        url = '/' + repo + '/' + action + '/' + branch + '/'
    }
    else if($.inArray(action, ['blob','tree'])>=0) {
        url = '/' + repo + '/' + action + '/' + branch + '/' + (path ? path : '');
    }
    else if(action == 'repo') {
        url = '/' + repo + '/tree/' + branch + '/'
    }
    window.location = url;
}
function init_clone_urls() {
    $('.urllink').each(function(index, elt) {
        $(elt).click(function() {
            $('#cloneurl').attr('value', $(this).children('span').html());
        });
    });
    $('#cloneurl').attr('value', $('.urllink').first().children('span').html());
}
