$('#countdown').countDown({
  separator: "",
  separator_days: ""
});

$('#participants-button').click(function() {
  $('.participants-container').toggleClass('hidden-xs');
  $(this).children().toggleClass('hidden');
});

$(document).ready(function() {

  $('body').scrollspy({target: '.sidenav'});

  var sideNav = $('.sidenav')

  sideNav.affix({
    offset: {
      top: function () {
        var offsetTop      = sideNav.offset().top;
        var sideBarMargin  = parseInt(sideNav.children(0).css('margin-top'), 10);

        return (this.top = offsetTop - sideBarMargin);
      }
    }
  });
});
