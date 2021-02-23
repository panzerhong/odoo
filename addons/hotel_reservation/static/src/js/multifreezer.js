$(document).ready(function () {
        $('.table-freeze-multi').each(function () {

            //Sopahnon This functions is to change url or eliminate id of the view
            function removeParam(key, sourceURL) {
                var rtn = sourceURL.split("#")[0],
                    param,
                    params_arr = [],
                    queryString = (sourceURL.indexOf("#") !== -1) ? sourceURL.split("#")[1] : "";
                if (queryString !== "") {
                    params_arr = queryString.split("&");
                    for (var i = params_arr.length - 1; i >= 0; i -= 1) {
                        param = params_arr[i].split("=")[0];
                        if (param === key) {
                            params_arr.splice(i, 1);
                        }
                    }
                    rtn = rtn + "#" + params_arr.join("&");
                    }
                 return rtn;
                }
            var path = window.location.href;
            var url2 = removeParam("id", path);
            var pathName = window.location.pathname;
            var replaceUrl = url2.split('#')[1];
            window.location.hash=replaceUrl;

            //end here//

            var table = $(this),
                scrollbarWidth = freezerGetScrollbarWidth();

            //prepare
            table.css({
                margin: 0
            }).addClass('table-freeze-multi-original').find('tfoot').remove();

            //wrap
            table.wrap('<div class="freeze-multi-scroll-wrapper" />');
            var wrapper = table.closest('.freeze-multi-scroll-wrapper');
            table.wrap('<div class="freeze-multi-scroll-table" />');
            table.wrap('<div class="freeze-multi-scroll-table-body" />');
            var scroller = wrapper.find('.freeze-multi-scroll-table-body');

            //layout
            var headblock = $('<div class="freeze-multi-scroll-table-head-inner" />');
            scroller.before($('<div class="freeze-multi-scroll-table-head" />').append(headblock));
            var topblock = $('<div class="freeze-multi-scroll-left-head" />');
            var leftblock = $('<div class="freeze-multi-scroll-left-body-inner" />');
            wrapper.append(
                $('<div class="freeze-multi-scroll-left" />')
                    .append(topblock)
                    .append($('<div class="freeze-multi-scroll-left-body" />').append(leftblock))
            );

            //cloning
            var clone = table.clone(true);
            clone.addClass('table-freeze-multi-clone').removeClass('table-freeze-multi-original');
            var colsNumber = table.data('colsNumber') || table.find('tbody tr:first th').length;
            //head
            var cloneHead = clone.clone(true);
            cloneHead.find('tbody').remove();
            headblock.append(cloneHead);
            //top
            var cloneTop = cloneHead.clone(true);
            topblock.append(cloneTop);
            //left
            var cloneLeft = clone.clone(true);
            cloneLeft.find('thead').remove();
            leftblock.append(cloneLeft);

            //sizing
            var scrollHeight = table.data('scrollHeight') || wrapper.parent().closest('*').height();
            var headerHeight = table.find('thead').height();
            var leftWidth = (function () {
                var w = 0;
                table.find('tbody tr:first > *').slice(0, colsNumber).each(function () {
                    w = w + $(this).outerWidth();
                });
                return w + 1;
            }());
            wrapper.css('height', scrollHeight);
            scroller.css('max-height', scrollHeight - headblock.height());
            headblock.width(table.width()).css('padding-right', scrollbarWidth);
            leftblock.add(leftblock.parent()).height(scrollHeight - scrollbarWidth - headerHeight);
            leftblock.width(leftWidth + scrollbarWidth);
            wrapper.find('.freeze-multi-scroll-left').width(leftWidth);

            //postprocess
            wrapper.find('.table-freeze-multi-original thead').hide();

            //scrolling
            scroller.on('scroll', function () {
                var s = $(this),
                    left = s.scrollLeft(),
                    top = s.scrollTop();
                headblock.css('transform', 'translate(' + (-1 * left) + 'px, 0)');
                leftblock.scrollTop(top);

            });
            leftblock.on('mousewheel', false);

        });
    });

// @see https://davidwalsh.name/detect-scrollbar-width

function freezerGetScrollbarWidth () {
    // Create the measurement node
    var scrollDiv = document.createElement("div");
    scrollDiv.className = "freezer-scrollbar-measure";
    document.body.appendChild(scrollDiv);

    // Get the scrollbar width
    var scrollbarWidth = scrollDiv.offsetWidth - scrollDiv.clientWidth;
    //console.warn(scrollbarWidth); // Mac: 15, Win: 17

    // Delete the DIV
    document.body.removeChild(scrollDiv);

    return scrollbarWidth;
}

 var _gaq = _gaq || [];
    _gaq.push(['_setAccount', 'UA-36251023-1']);
    _gaq.push(['_setDomainName', 'jqueryscript.net']);
    _gaq.push(['_trackPageview']);

    (function () {
        var ga = document.createElement('script');
        ga.type = 'text/javascript';
        ga.async = true;
        ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
        var s = document.getElementsByTagName('script')[0];
        s.parentNode.insertBefore(ga, s);
    })();