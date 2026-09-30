(() => {
  const LIST_SELECTOR = ".ai-conversation-list";
  const TRIGGER_CLASS = "ai-conversation-menu-trigger";
  const MENU_CLASS = "ai-conversation-menu";
  const SIDEBAR_WIDTH_KEY = "dental-ai-sidebar-width";
  const COPY_ICON = '<svg width="21" height="21" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M13.468 11.1216C13.468 10.4107 13.468 9.91717 13.4367 9.53369C13.4137 9.25191 13.3758 9.0622 13.3244 8.91846L13.2687 8.78858C13.1148 8.48652 12.8803 8.23344 12.593 8.05713L12.466 7.98584C12.308 7.90546 12.0963 7.84854 11.7209 7.81787C11.3374 7.78656 10.8439 7.78662 10.133 7.78662H7.29999C6.58895 7.78662 6.09562 7.78654 5.7121 7.81787C5.43015 7.84091 5.24064 7.87872 5.09686 7.93018L4.96698 7.98584C4.66487 8.13977 4.41184 8.37419 4.23554 8.66162L4.16522 8.78858C4.08477 8.94657 4.02794 9.15811 3.99725 9.53369C3.96594 9.91718 3.96503 10.4107 3.96503 11.1216V13.9546C3.96503 14.6656 3.96592 15.159 3.99725 15.5425C4.02796 15.9182 4.08471 16.1296 4.16522 16.2876L4.23554 16.4136C4.41185 16.7012 4.66472 16.9353 4.96698 17.0894L5.09686 17.146C5.24061 17.1974 5.43024 17.2343 5.7121 17.2573C6.09562 17.2887 6.58895 17.2896 7.29999 17.2896H10.133C10.8439 17.2896 11.3374 17.2886 11.7209 17.2573C12.0965 17.2266 12.308 17.1698 12.466 17.0894L12.593 17.019C12.8804 16.8427 13.1148 16.5897 13.2687 16.2876L13.3244 16.1577C13.3759 16.0139 13.4137 15.8244 13.4367 15.5425C13.468 15.159 13.468 14.6656 13.468 13.9546V11.1216ZM14.798 13.1196C15.2528 13.118 15.6011 13.1147 15.8879 13.0913C16.2634 13.0606 16.475 13.0038 16.633 12.9233L16.759 12.8521C17.0466 12.6757 17.2808 12.4228 17.4348 12.1206L17.4914 11.9907C17.5428 11.847 17.5797 11.6572 17.6027 11.3755C17.634 10.992 17.6349 10.4985 17.6349 9.7876V6.95459C17.6349 6.24355 17.6341 5.75022 17.6027 5.3667C17.5797 5.08484 17.5428 4.89522 17.4914 4.75147L17.4348 4.62158C17.2807 4.31933 17.0466 4.06645 16.759 3.89014L16.633 3.81982C16.475 3.73932 16.2636 3.68256 15.8879 3.65186C15.5044 3.62052 15.011 3.61963 14.3 3.61963H11.467C10.7561 3.61963 10.2626 3.62054 9.87909 3.65186C9.59738 3.67487 9.40759 3.71179 9.26386 3.76318L9.13397 3.81982C8.83175 3.97382 8.57885 4.20802 8.40253 4.49561L8.33124 4.62158C8.25079 4.77957 8.19396 4.99114 8.16327 5.3667C8.13984 5.65352 8.13561 6.00178 8.13397 6.45654H10.133C10.822 6.45654 11.3791 6.4559 11.8293 6.49268C12.2873 6.5301 12.6937 6.6093 13.0705 6.80127L13.2883 6.92334C13.7839 7.22739 14.1878 7.66313 14.4533 8.18408L14.5197 8.32666C14.6642 8.66318 14.7291 9.02433 14.7619 9.42529C14.7987 9.8755 14.798 10.4326 14.798 11.1216V13.1196ZM18.965 9.7876C18.965 10.4766 18.9657 11.0337 18.9289 11.4839C18.8961 11.8848 18.8311 12.246 18.6867 12.5825L18.6203 12.7251C18.3548 13.246 17.9509 13.6818 17.4553 13.9858L17.2365 14.1079C16.8599 14.2998 16.4541 14.3791 15.9963 14.4165C15.6592 14.444 15.2624 14.4481 14.7951 14.4497C14.7935 14.917 14.7894 15.3138 14.7619 15.6509C14.7292 16.0516 14.664 16.4122 14.5197 16.7485L14.4533 16.8911C14.1878 17.4122 13.7841 17.8487 13.2883 18.1528L13.0705 18.2749C12.6937 18.4669 12.2873 18.5461 11.8293 18.5835C11.3791 18.6203 10.822 18.6196 10.133 18.6196H7.29999C6.6109 18.6196 6.05394 18.6203 5.6037 18.5835C5.20305 18.5508 4.84233 18.4855 4.50604 18.3413L4.36347 18.2749C3.84243 18.0094 3.40584 17.6056 3.10175 17.1099L2.97968 16.8911C2.78787 16.5145 2.70849 16.1087 2.67108 15.6509C2.6343 15.2006 2.63495 14.6437 2.63495 13.9546V11.1216C2.63495 10.4326 2.63431 9.8755 2.67108 9.42529C2.7085 8.96729 2.78771 8.56084 2.97968 8.18408L3.10175 7.96631C3.40585 7.47049 3.84235 7.06679 4.36347 6.80127L4.50604 6.73486C4.84236 6.59059 5.20302 6.52542 5.6037 6.49268C5.9405 6.46516 6.33707 6.4601 6.80389 6.4585C6.8055 5.99167 6.81056 5.5951 6.83807 5.2583C6.87549 4.80047 6.95482 4.39471 7.14667 4.01807L7.26874 3.79932C7.5728 3.30371 8.00855 2.89973 8.52948 2.63428L8.67206 2.56787C9.00854 2.42345 9.36978 2.35844 9.77069 2.32568C10.2209 2.28891 10.778 2.28955 11.467 2.28955H14.3C14.9891 2.28955 15.546 2.2889 15.9963 2.32568C16.4541 2.3631 16.8599 2.44247 17.2365 2.63428L17.4553 2.75635C17.951 3.06044 18.3548 3.49703 18.6203 4.01807L18.6867 4.16065C18.8309 4.49694 18.8962 4.85765 18.9289 5.2583C18.9657 5.70854 18.965 6.2655 18.965 6.95459V9.7876Z" fill="currentColor"></path></svg>';
  const RETRY_ICON = '<svg aria-hidden="true" height="16" viewBox="0 0 16 16" width="16" xmlns="http://www.w3.org/2000/svg"><path d="M14.0219 8.22363C14.3094 8.25975 14.5128 8.52209 14.477 8.80957C14.0729 12.0322 11.311 14.5222 7.96723 14.5225C6.11053 14.5225 4.40157 13.752 3.19184 12.5146V13.9961C3.19184 14.286 2.9564 14.5215 2.66645 14.5215C2.37668 14.5213 2.14106 14.2859 2.14106 13.9961V11.4961C2.14122 10.9303 2.60064 10.4709 3.16645 10.4707H5.66645C5.9563 10.4707 6.19167 10.7063 6.19184 10.9961C6.19184 11.286 5.9564 11.5215 5.66645 11.5215H3.70356C4.72588 12.7119 6.27317 13.4717 7.96723 13.4717C10.7796 13.4715 13.0975 11.3782 13.436 8.67871C13.4724 8.39145 13.7345 8.18763 14.0219 8.22363Z" fill="currentColor"></path><path d="M13.3334 1.47461C13.6234 1.47461 13.8588 1.71005 13.8588 2V4.5C13.8588 5.06609 13.3995 5.52539 12.8334 5.52539H10.3334C10.0435 5.52534 9.80805 5.28992 9.80805 5C9.80805 4.71008 10.0435 4.47466 10.3334 4.47461H12.2905C11.2691 3.28567 9.72356 2.52743 8.03168 2.52734C5.22176 2.52746 2.90507 4.61922 2.56684 7.31738C2.53053 7.60481 2.26843 7.80851 1.9809 7.77246C1.69351 7.73623 1.48997 7.47397 1.52582 7.18652C1.9297 3.96546 4.69011 1.47668 8.03168 1.47656C9.88918 1.47665 11.5991 2.24798 12.8081 3.4873V2C12.8081 1.71008 13.0435 1.47466 13.3334 1.47461Z" fill="currentColor"></path></svg>';
  const BRANCH_ICON = '<svg aria-hidden="true" height="16" viewBox="0 0 16 16" width="16" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M11.6672 1.97461C12.7854 1.97487 13.6926 2.88179 13.6926 4C13.6926 5.01485 12.9449 5.85303 11.9709 6H12.1917V6.13379C12.1914 7.45442 11.1207 8.52532 9.80005 8.52539H6.19946C5.45895 8.52577 4.85889 9.12567 4.85864 9.86621V10.0449C5.72223 10.2765 6.35864 11.0635 6.35864 12C6.35864 13.1184 5.45163 14.0254 4.33325 14.0254C3.21488 14.0254 2.30786 13.1184 2.30786 12C2.30786 11.0635 2.94428 10.2765 3.80786 10.0449V5.9541C2.9444 5.72243 2.30786 4.93645 2.30786 4C2.30786 2.88162 3.21488 1.97461 4.33325 1.97461C5.45163 1.97461 6.35864 2.88162 6.35864 4C6.35864 4.93645 5.7221 5.72243 4.85864 5.9541V7.88574C5.24104 7.62624 5.70264 7.47475 6.19946 7.47461H9.80005C10.5408 7.47454 11.1416 6.87452 11.1418 6.13379V6H11.3625C10.3886 5.85303 9.64185 5.01485 9.64185 4C9.64185 2.88162 10.5489 1.97461 11.6672 1.97461ZM4.33325 11.0254C3.79477 11.0254 3.35864 11.4615 3.35864 12C3.35864 12.5385 3.79477 12.9746 4.33325 12.9746C4.87173 12.9746 5.30786 12.5385 5.30786 12C5.30786 11.4615 4.87173 11.0254 4.33325 11.0254ZM4.33325 3.02539C3.79477 3.02539 3.35864 3.46152 3.35864 4C3.35864 4.53848 3.79477 4.97461 4.33325 4.97461C4.87173 4.97461 5.30786 4.53848 5.30786 4C5.30786 3.46152 4.87173 3.02539 4.33325 3.02539ZM11.6672 3.02539C11.1288 3.02539 10.6926 3.46152 10.6926 4C10.6926 4.53848 11.1288 4.97461 11.6672 4.97461C12.2055 4.97435 12.6418 4.53831 12.6418 4C12.6418 3.46169 12.2055 3.02565 11.6672 3.02539Z" fill="currentColor"></path></svg>';
  const EDIT_ICON = '<svg width="21" height="21" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M11.7313 4.20472C13.1489 2.92391 15.3377 2.96644 16.7039 4.33265L16.8318 4.46742C18.0713 5.8393 18.0713 7.93343 16.8318 9.30531L16.7039 9.44007L10.4119 15.7311C10.0884 16.0546 9.85387 16.2917 9.62188 16.4821L9.3875 16.6588C9.18236 16.799 8.96432 16.9196 8.73711 17.0192L8.50762 17.1119C8.32585 17.1785 8.13845 17.2266 7.92168 17.2711L7.15703 17.4069L4.76348 17.8053C4.62062 17.8291 4.46916 17.8552 4.34063 17.8649C4.24185 17.8723 4.10835 17.875 3.9627 17.8395L3.81426 17.7907C3.59124 17.695 3.40749 17.5271 3.2918 17.316L3.2459 17.2223C3.1596 17.0209 3.16176 16.8276 3.17168 16.6959C3.18138 16.5674 3.20744 16.4159 3.23125 16.2731L3.62969 13.8795L3.76445 13.1149C3.80902 12.898 3.85797 12.7108 3.92461 12.5289L4.01738 12.2985C4.11693 12.0715 4.23774 11.854 4.37774 11.6491L4.55352 11.4147C4.74395 11.1825 4.98173 10.9484 5.30547 10.6246L11.5965 4.33265L11.7313 4.20472ZM6.2459 11.5651C5.89673 11.9142 5.71261 12.0998 5.58672 12.2526L5.47539 12.3991C5.38197 12.5358 5.30159 12.6812 5.23516 12.8327L5.17363 12.9869C5.1333 13.0971 5.1025 13.2125 5.06817 13.3815L4.94121 14.0983L4.54277 16.4918L4.5418 16.4938H4.54473L6.93828 16.0944L7.65508 15.9684C7.82408 15.9341 7.93949 15.9033 8.04961 15.8629L8.20293 15.8014C8.35464 15.7349 8.49956 15.6538 8.63652 15.5602L8.78399 15.4498C8.93677 15.3239 9.12233 15.1398 9.47149 14.7907L14.4588 9.80238L11.2332 6.57679L6.2459 11.5651ZM15.7635 5.27308C14.9282 4.43776 13.6058 4.38573 12.7098 5.11683L12.5369 5.27308L12.1736 5.63636L15.4002 8.86195L15.7635 8.49964L15.9197 8.32581C16.6016 7.48961 16.6016 6.28311 15.9197 5.44691L15.7635 5.27308Z" fill="currentColor"></path></svg>';
  const REFRESH_ICON = RETRY_ICON;
  const SEND_ICON = '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 14.25V3.75M9 3.75L4.75 8M9 3.75L13.25 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const STOP_ICON = '<svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14"><rect x="3" y="3" width="8" height="8" rx="1.5" fill="currentColor"/></svg>';
  const SEARCH_ICON = '<svg data-no-autosize="true" aria-hidden="true" focusable="false" height="20" viewBox="0 0 20 20" width="20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M9.16125 2.37891C12.8651 2.37908 15.8673 5.38206 15.8673 9.08594C15.8672 10.7162 15.2847 12.2098 14.3175 13.3721L17.5597 16.6152C17.8194 16.8749 17.8194 17.296 17.5597 17.5557C17.3 17.8152 16.8789 17.8153 16.6193 17.5557L13.3683 14.3057C12.2176 15.2343 10.7551 15.7919 9.16125 15.792C5.45737 15.792 2.4544 12.7898 2.45422 9.08594C2.45422 5.38195 5.45727 2.37891 9.16125 2.37891ZM9.16125 3.70898C6.1918 3.70898 3.7843 6.11649 3.7843 9.08594C3.78448 12.0552 6.19191 14.4619 9.16125 14.4619C12.1304 14.4617 14.5371 12.0551 14.5372 9.08594C14.5372 6.1166 12.1306 3.70916 9.16125 3.70898Z" fill="currentColor"></path></svg>';
  const NEW_CHAT_ICON = '<svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M8.16675 2.50127C8.53391 2.50127 8.83161 2.7992 8.83179 3.16631C8.83179 3.53358 8.53402 3.83135 8.16675 3.83135H5.83374C4.72836 3.83135 3.83197 4.72797 3.83179 5.8333V14.1663C3.83179 15.2718 4.72825 16.1683 5.83374 16.1683H14.1667C15.2722 16.1683 16.1687 15.2718 16.1687 14.1663V11.8333C16.1689 11.4662 16.4666 11.1683 16.8337 11.1683C17.2007 11.1684 17.4986 11.4663 17.4988 11.8333V14.1663C17.4988 16.0063 16.0068 17.4983 14.1667 17.4983H5.83374C3.99371 17.4983 2.50171 16.0063 2.50171 14.1663V5.8333C2.50189 3.99343 3.99382 2.50127 5.83374 2.50127H8.16675Z"></path><path fill-rule="evenodd" clip-rule="evenodd" d="M13.4265 3.10381C14.3857 2.15908 15.9276 2.16466 16.8796 3.11651C17.8339 4.07106 17.8372 5.61827 16.8865 6.57647L11.7244 11.7786C11.3005 12.2058 10.7622 12.5027 10.1746 12.6321L7.78784 13.1565C7.20661 13.2842 6.6889 12.766 6.81714 12.1849L7.34253 9.80498C7.47294 9.21426 7.77197 8.67391 8.20288 8.24932L13.4265 3.10381ZM15.9392 4.05694C15.5038 3.62172 14.7988 3.61907 14.3601 4.05108L9.13647 9.19659C8.88861 9.44077 8.71644 9.75138 8.64136 10.0911L8.28979 11.6849L9.88843 11.3333C10.2265 11.2588 10.5362 11.0878 10.78 10.8421L15.9421 5.63897C16.3769 5.20075 16.3756 4.49352 15.9392 4.05694Z"></path></svg>';
  const CONVERSATION_ICON = '<svg aria-hidden="true" focusable="false" height="20" viewBox="0 0 20 20" width="20" xmlns="http://www.w3.org/2000/svg"><path d="M16.835 9.99963C16.8348 6.49033 13.8111 3.58167 10 3.58167C6.18893 3.58167 3.16523 6.49033 3.16504 9.99963C3.16504 11.4141 3.73237 12.3498 4.44727 13.7653C4.53356 13.9364 4.55818 14.1326 4.5166 14.3199L4.19043 15.7887L5.78027 15.3776L5.9248 15.3531C6.02169 15.3457 6.11884 15.3556 6.21191 15.3815L6.34766 15.4323L6.80664 15.6442C7.86864 16.1161 8.86618 16.4186 10 16.4186C13.8112 16.4186 16.835 13.5091 16.835 9.99963ZM18.165 9.99963C18.165 14.3142 14.4731 17.7487 10 17.7487C8.47948 17.7487 7.19622 17.2956 5.94043 16.7086L3.73633 17.2809C3.13492 17.4368 2.58124 16.9021 2.71582 16.2955L3.17871 14.2067C2.53737 12.9532 1.83496 11.7286 1.83496 9.99963C1.83515 5.6852 5.52703 2.25159 10 2.25159C14.473 2.25159 18.1649 5.6852 18.165 9.99963Z" fill="currentColor"></path></svg>';
  const CLOSE_ICON = '<svg aria-hidden="true" focusable="false" height="20" viewBox="0 0 20 20" width="20" xmlns="http://www.w3.org/2000/svg"><path d="M13.6964 5.36252C13.9561 5.10319 14.3782 5.10304 14.6378 5.36252C14.8974 5.62211 14.8972 6.0442 14.6378 6.30393L10.9405 10.0002L14.6368 13.6965C14.8964 13.9562 14.8965 14.3773 14.6368 14.6369C14.3772 14.8966 13.9561 14.8965 13.6964 14.6369L10.0001 10.9406L6.30381 14.6369C6.0441 14.8965 5.62302 14.8966 5.36338 14.6369C5.10384 14.3773 5.10388 13.9562 5.36338 13.6965L9.05869 10.0002L5.3624 6.30393C5.10314 6.0442 5.10285 5.62208 5.3624 5.36252C5.62195 5.10297 6.04407 5.10326 6.30381 5.36252L10.0001 9.05881L13.6964 5.36252Z" fill="currentColor"></path></svg>';
  const nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;

  function closeMenu() {
    document.querySelector(`.${MENU_CLASS}`)?.remove();
  }

  function setNativeField(selector, value) {
    const field = document.querySelector(selector);
    if (!field) return false;
    if (nativeTextareaValueSetter && field instanceof HTMLTextAreaElement) nativeTextareaValueSetter.call(field, value);
    else if (nativeInputValueSetter && field instanceof HTMLInputElement) nativeInputValueSetter.call(field, value);
    else field.value = value;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function clickHiddenAction(selector) {
    const component = document.querySelector(selector);
    const button = component?.matches("button") ? component : component?.querySelector("button");
    button?.click();
  }

  let searchDialog = null;
  let searchResultSignature = "";
  let searchQuery = "";
  let searchSourceItems = [];
  let floatingTooltip = null;
  let tooltipAnchor = null;

  function hideFloatingTooltip() {
    tooltipAnchor?.removeAttribute("aria-describedby");
    floatingTooltip?.remove();
    tooltipAnchor = null;
    floatingTooltip = null;
  }

  function showFloatingTooltip(anchor) {
    const text = anchor.dataset.tooltip?.trim();
    if (!text) return;
    hideFloatingTooltip();
    const tooltip = document.createElement("div");
    tooltip.id = `ai-tooltip-${Date.now()}`;
    tooltip.className = "ai-floating-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = text;
    document.body.append(tooltip);
    const anchorRect = anchor.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const roomAbove = anchorRect.top - tooltipRect.height - 9;
    const top = roomAbove >= 8 ? roomAbove : anchorRect.bottom + 9;
    const idealLeft = anchorRect.left + (anchorRect.width - tooltipRect.width) / 2;
    const left = Math.min(innerWidth - tooltipRect.width - 8, Math.max(8, idealLeft));
    tooltip.style.left = `${Math.round(left)}px`;
    tooltip.style.top = `${Math.round(top)}px`;
    anchor.setAttribute("aria-describedby", tooltip.id);
    tooltipAnchor = anchor;
    floatingTooltip = tooltip;
    requestAnimationFrame(() => tooltip.classList.add("is-visible"));
  }

  function initializeFloatingTooltips(root = document) {
    root.querySelectorAll(".ai-search-open, .ai-new-chat-proxy, .ai-search-close").forEach((button) => {
      if (button.dataset.aiTooltipReady === "true") return;
      button.dataset.aiTooltipReady = "true";
      button.addEventListener("pointerenter", () => showFloatingTooltip(button));
      button.addEventListener("pointerleave", hideFloatingTooltip);
      button.addEventListener("focus", () => showFloatingTooltip(button));
      button.addEventListener("blur", hideFloatingTooltip);
    });
  }

  function conversationItems() {
    return [...document.querySelectorAll(`${LIST_SELECTOR} label`)].map((label) => ({
      label,
      title: currentTitle(label),
      value: label.querySelector('input[type="radio"]')?.value || currentTitle(label),
    })).filter((item) => item.title);
  }

  function renderSearchResults() {
    if (!searchDialog?.isConnected) return;
    if (!searchSourceItems.length || searchSourceItems.some((item) => !item.label.isConnected)) {
      searchSourceItems = conversationItems();
    }
    const normalizedQuery = searchQuery.trim().toLocaleLowerCase();
    const items = normalizedQuery
      ? searchSourceItems.filter((item) => item.title.toLocaleLowerCase().includes(normalizedQuery))
      : searchSourceItems;
    const signature = `${normalizedQuery}\u0002${items.map((item) => `${item.value}\u0000${item.title}`).join("\u0001")}`;
    if (signature === searchResultSignature) return;
    searchResultSignature = signature;
    const results = searchDialog.querySelector(".ai-search-results");
    if (!results) return;
    if (!items.length) {
      results.innerHTML = '<p class="ai-search-empty">没有匹配的对话</p>';
      return;
    }
    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ai-search-result";
      button.setAttribute("role", "option");
      button.innerHTML = `<span class="ai-search-result-icon">${CONVERSATION_ICON}</span><span></span>`;
      button.lastElementChild.textContent = item.title;
      button.addEventListener("click", () => {
        const radio = item.label.querySelector('input[type="radio"]');
        if (radio && !radio.checked) radio.click();
        closeSearchDialog();
      });
      fragment.append(button);
    });
    results.replaceChildren(fragment);
  }

  function closeSearchDialog() {
    if (!searchDialog) return;
    hideFloatingTooltip();
    searchDialog.remove();
    searchDialog = null;
    searchResultSignature = "";
    searchQuery = "";
    searchSourceItems = [];
    document.body.classList.remove("ai-search-dialog-open");
  }

  function openSearchDialog() {
    if (searchDialog?.isConnected) {
      searchDialog.querySelector("input")?.focus();
      return;
    }
    closeMenu();
    const overlay = document.createElement("div");
    overlay.className = "ai-search-overlay";
    overlay.innerHTML = `
      <section class="ai-search-dialog" role="dialog" aria-modal="true" aria-labelledby="ai-search-dialog-title">
        <h2 id="ai-search-dialog-title" class="ai-visually-hidden">搜索对话</h2>
        <header class="ai-search-dialog-header">
          <label class="ai-visually-hidden" for="ai-search-dialog-input">搜索对话</label>
          <input id="ai-search-dialog-input" type="search" placeholder="搜索…" autocomplete="off" spellcheck="false" />
          <button type="button" class="ai-search-close" aria-label="关闭搜索" data-tooltip="关闭搜索">${CLOSE_ICON}</button>
        </header>
        <div class="ai-search-dialog-body">
          <div class="ai-search-dialog-label">最近对话</div>
          <div class="ai-search-results" role="listbox"></div>
        </div>
      </section>`;
    document.body.append(overlay);
    searchDialog = overlay;
    searchResultSignature = "";
    searchQuery = "";
    searchSourceItems = conversationItems();
    document.body.classList.add("ai-search-dialog-open");
    const input = overlay.querySelector("input");
    const close = overlay.querySelector(".ai-search-close");
    input.addEventListener("input", () => {
      searchResultSignature = "";
      searchQuery = input.value;
      renderSearchResults();
    });
    close.addEventListener("click", () => closeSearchDialog());
    overlay.addEventListener("pointerdown", (event) => {
      if (event.target === overlay) closeSearchDialog();
    });
    renderSearchResults();
    initializeFloatingTooltips(overlay);
    requestAnimationFrame(() => input.focus());
  }

  function currentTitle(label) {
    const text = label.querySelector(":scope > span")?.textContent?.trim() || "";
    return text.split(/\s+·\s+/u)[0].trim();
  }

  function positionMenu(menu, label) {
    const rect = label.getBoundingClientRect();
    const width = menu.classList.contains("is-renaming") ? 264 : 188;
    const roomOnRight = innerWidth - rect.right;
    const left = roomOnRight >= width + 12
      ? rect.right + 6
      : Math.max(12, rect.left - width - 6);
    menu.style.left = `${left}px`;
    menu.style.top = `${Math.max(12, Math.min(rect.top, innerHeight - menu.offsetHeight - 12))}px`;
  }

  function showRenameEditor(menu, label) {
    menu.classList.add("is-renaming");
    const editor = document.createElement("div");
    editor.className = "ai-conversation-menu-editor";
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = 80;
    input.value = currentTitle(label);
    input.setAttribute("aria-label", "新的对话名称");
    const actions = document.createElement("div");
    actions.className = "ai-conversation-menu-editor-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "取消";
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "保存";
    save.className = "is-primary";
    actions.append(cancel, save);
    editor.append(input, actions);
    menu.replaceChildren(editor);
    positionMenu(menu, label);
    input.focus();
    input.select();
    cancel.addEventListener("click", closeMenu);
    const commit = () => {
      const value = input.value.trim();
      if (!value || !setNativeField(".ai-conversation-title textarea, .ai-conversation-title input", value)) return;
      clickHiddenAction(".ai-conversation-rename-action");
      closeMenu();
    };
    save.addEventListener("click", commit);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") commit();
      if (event.key === "Escape") closeMenu();
    });
  }

  function openMenu(trigger, label) {
    closeMenu();
    const radio = label.querySelector('input[type="radio"]');
    if (radio && !radio.checked) radio.click();
    const menu = document.createElement("div");
    menu.className = MENU_CLASS;
    menu.setAttribute("role", "menu");
    const rename = document.createElement("button");
    rename.type = "button";
    rename.textContent = "重命名";
    rename.setAttribute("role", "menuitem");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "删除";
    remove.className = "is-danger";
    remove.setAttribute("role", "menuitem");
    menu.append(rename, remove);
    document.body.append(menu);
    positionMenu(menu, label);
    rename.addEventListener("click", () => showRenameEditor(menu, label));
    remove.addEventListener("click", () => {
      if (remove.dataset.confirmed !== "true") {
        remove.dataset.confirmed = "true";
        remove.textContent = "再次点击确认删除";
        return;
      }
      clickHiddenAction(".ai-conversation-delete-action");
      closeMenu();
    });
  }

  function decorateConversationItems(root = document) {
    root.querySelectorAll(`${LIST_SELECTOR} label`).forEach((label) => {
      if (label.querySelector(`.${TRIGGER_CLASS}`)) return;
      const trigger = document.createElement("button");
      trigger.type = "button";
      trigger.className = TRIGGER_CLASS;
      trigger.textContent = "⋯";
      trigger.title = "管理对话";
      trigger.setAttribute("aria-label", "管理对话");
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openMenu(trigger, label);
      });
      label.append(trigger);
    });
  }

  function iconButton(className, label, icon) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `ai-message-action ${className}`;
    button.setAttribute("aria-label", label);
    button.dataset.tooltip = label;
    button.innerHTML = icon;
    return button;
  }

  function nativeMessageAction(row, expected) {
    const controls = row.nextElementSibling;
    if (!controls?.classList.contains("message-buttons")) return null;
    return [...controls.querySelectorAll("button")].find((button) => {
      const name = `${button.getAttribute("aria-label") || ""} ${button.title || ""}`.toLowerCase();
      return expected.some((value) => name.includes(value));
    }) || null;
  }

  function formatMessageTime(row) {
    const marker = row.querySelector(".ai-message-time-marker");
    const encoded = [...(marker?.classList || [])].find((name) => /^ai-chat-time-\d{8}T\d{4}$/u.test(name));
    const match = encoded?.match(/^ai-chat-time-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})$/u);
    const timestamp = match ? `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}` : "";
    if (timestamp) {
      const value = new Date(timestamp);
      if (!Number.isNaN(value.getTime())) {
        const now = new Date();
        const day = new Date(value.getFullYear(), value.getMonth(), value.getDate());
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const diff = Math.round((today - day) / 86400000);
        const time = value.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
        if (diff === 0) return `今天 ${time}`;
        if (diff === 1) return `昨天 ${time}`;
        return `${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")} ${time}`;
      }
    }
    const selected = document.querySelector(`${LIST_SELECTOR} input:checked`)?.closest("label")?.textContent || "";
    const fallback = selected.match(/(\d{2}-\d{2}\s+\d{2}:\d{2})/u);
    return fallback ? fallback[1] : "刚刚";
  }

  async function copyMessage(row, button) {
    const content = row.querySelector(".message-content")?.innerText?.trim() || "";
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      button.dataset.tooltip = "已复制";
      setTimeout(() => { button.dataset.tooltip = "复制"; }, 1200);
    } catch (_) {
      nativeMessageAction(row, ["copy", "复制"])?.click();
    }
  }

  function branchFrom(row) {
    const rows = [...row.closest('[role="log"]')?.querySelectorAll(".message-row") || []];
    const index = rows.indexOf(row);
    if (index < 0 || !setNativeField(".ai-branch-index textarea, .ai-branch-index input", String(index))) return;
    clickHiddenAction(".ai-branch-action");
  }

  function decorateChatMessages(root = document) {
    root.querySelectorAll(".ai-chat-thread .message-row").forEach((row) => {
      if (row.dataset.aiDecorated === "true") return;
      row.dataset.aiDecorated = "true";
      const isUser = row.classList.contains("user-row");
      const time = document.createElement("div");
      time.className = "ai-message-time";
      time.textContent = formatMessageTime(row);
      row.prepend(time);
      const actions = document.createElement("div");
      actions.className = "ai-message-actions";
      const copy = iconButton("is-copy", "复制", COPY_ICON);
      copy.addEventListener("click", () => copyMessage(row, copy));
      actions.append(copy);
      if (isUser) {
        const edit = iconButton("is-edit", "编辑", EDIT_ICON);
        edit.addEventListener("click", () => nativeMessageAction(row, ["edit", "编辑"])?.click());
        actions.append(edit);
      } else {
        const retry = iconButton("is-retry", "重试", RETRY_ICON);
        retry.addEventListener("click", () => nativeMessageAction(row, ["retry", "重试"])?.click());
        const branch = iconButton("is-branch", "在新对话中创建分支", BRANCH_ICON);
        branch.addEventListener("click", () => branchFrom(row));
        actions.append(retry, branch);
      }
      row.append(actions);
    });
  }

  function applyFollowupPrompt(prompt) {
    const value = prompt?.trim() || "";
    if (!value || !setNativeField(".ai-composer-input textarea", value)) return;
    const selectedAction = document.querySelector(
      '.settings-followup-click-action input[type="radio"]:checked'
    )?.value;
    if (selectedAction === "直接发送") {
      requestAnimationFrame(() => clickHiddenAction(".ai-send-button"));
    } else {
      document.querySelector(".ai-composer-input textarea")?.focus();
    }
  }

  function initializeMessageFollowups(root = document) {
    root.querySelectorAll(".ai-message-followup").forEach((button) => {
      if (button.dataset.aiFollowupReady === "true") return;
      button.dataset.aiFollowupReady = "true";
      button.addEventListener("click", () => applyFollowupPrompt(button.dataset.followup));
    });
    root.querySelectorAll(".ai-suggestion-chip button").forEach((button) => {
      if (button.dataset.aiFollowupReady === "true") return;
      button.dataset.aiFollowupReady = "true";
      button.addEventListener("click", () => applyFollowupPrompt(button.textContent));
    });
  }

  function decorateStaticButtons(root = document) {
    const specs = [
      [".ai-conversation-refresh-button", "刷新最近对话", REFRESH_ICON],
      [".ai-send-button", "发送消息", SEND_ICON],
      [".ai-stop-button", "停止生成", STOP_ICON],
    ];
    specs.forEach(([selector, label, icon]) => {
      const component = root.querySelector(selector);
      const button = component?.matches("button") ? component : component?.querySelector("button");
      if (!button || button.dataset.aiIconReady === "true") return;
      button.dataset.aiIconReady = "true";
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
      button.innerHTML = icon;
    });
    root.querySelectorAll(".ai-search-open").forEach((button) => {
      if (button.dataset.aiIconReady === "true") return;
      button.dataset.aiIconReady = "true";
      button.innerHTML = SEARCH_ICON;
      button.addEventListener("click", openSearchDialog);
    });
    root.querySelectorAll(".ai-new-chat-proxy").forEach((button) => {
      if (button.dataset.aiIconReady === "true") return;
      button.dataset.aiIconReady = "true";
      button.innerHTML = NEW_CHAT_ICON;
      button.addEventListener("click", () => clickHiddenAction(".ai-new-chat-button"));
    });
  }

  function initializeComposerKeyboard(root = document) {
    root.querySelectorAll(".ai-composer-input textarea").forEach((textarea) => {
      if (textarea.dataset.aiKeyboardReady === "true") return;
      textarea.dataset.aiKeyboardReady = "true";
      textarea.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.isComposing || event.keyCode === 229) return;
        if (event.shiftKey) {
          event.preventDefault();
          event.stopImmediatePropagation();
          const start = textarea.selectionStart;
          const end = textarea.selectionEnd;
          textarea.setRangeText("\n", start, end, "end");
          textarea.dispatchEvent(new InputEvent("input", {
            bubbles: true,
            inputType: "insertLineBreak",
          }));
          return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!textarea.value.trim()) return;
        const component = document.querySelector(".ai-send-button");
        const button = component?.matches("button") ? component : component?.querySelector("button");
        if (button && !button.disabled) button.click();
      }, true);
    });
  }

  function sidebarBounds(layout) {
    const minimum = 240;
    const maximum = Math.max(minimum, Math.min(480, layout.clientWidth - 520));
    return { minimum, maximum };
  }

  function setSidebarWidth(layout, resizer, requestedWidth, persist = false) {
    const { minimum, maximum } = sidebarBounds(layout);
    const width = Math.round(Math.min(maximum, Math.max(minimum, requestedWidth)));
    layout.style.setProperty("--ai-sidebar-width", `${width}px`);
    layout.classList.toggle("ai-sidebar-compact", width < 340);
    resizer.setAttribute("aria-valuemin", String(minimum));
    resizer.setAttribute("aria-valuemax", String(maximum));
    resizer.setAttribute("aria-valuenow", String(width));
    if (persist) {
      try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(width)); } catch (_) { /* layout still works */ }
    }
  }

  function storedSidebarWidth() {
    try {
      const value = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY));
      return Number.isFinite(value) ? value : 300;
    } catch (_) {
      return 300;
    }
  }

  function initializeSidebarResizer(root = document) {
    root.querySelectorAll(".ai-sidebar-resizer").forEach((resizer) => {
      if (resizer.dataset.ready === "true") return;
      const layout = resizer.closest(".ai-chat-layout");
      if (!layout) return;
      resizer.dataset.ready = "true";
      setSidebarWidth(layout, resizer, storedSidebarWidth());
      resizer.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        const layoutRect = layout.getBoundingClientRect();
        let latestWidth = Number(resizer.getAttribute("aria-valuenow")) || 300;
        resizer.classList.add("is-dragging");
        document.body.classList.add("ai-sidebar-resizing");
        const move = (moveEvent) => {
          latestWidth = moveEvent.clientX - layoutRect.left;
          setSidebarWidth(layout, resizer, latestWidth);
        };
        const finish = () => {
          setSidebarWidth(layout, resizer, latestWidth, true);
          resizer.classList.remove("is-dragging");
          document.body.classList.remove("ai-sidebar-resizing");
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", finish);
          window.removeEventListener("pointercancel", finish);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", finish);
        window.addEventListener("pointercancel", finish);
      });
      resizer.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const current = Number(resizer.getAttribute("aria-valuenow")) || 300;
        setSidebarWidth(layout, resizer, current + (event.key === "ArrowLeft" ? -16 : 16), true);
      });
      resizer.addEventListener("dblclick", () => setSidebarWidth(layout, resizer, 300, true));
      new ResizeObserver(() => {
        const current = Number(resizer.getAttribute("aria-valuenow")) || 300;
        setSidebarWidth(layout, resizer, current);
      }).observe(layout);
    });
  }

  function initializeWorkspace(root = document) {
    decorateConversationItems(root);
    decorateChatMessages(root);
    initializeMessageFollowups(root);
    decorateStaticButtons(root);
    initializeComposerKeyboard(root);
    initializeSidebarResizer(root);
    initializeFloatingTooltips(root);
    renderSearchResults();
  }

  document.addEventListener("pointerdown", (event) => {
    const path = event.composedPath();
    if (!path.some((node) => node instanceof Element && (node.classList.contains(MENU_CLASS) || node.classList.contains(TRIGGER_CLASS)))) closeMenu();
  }, true);
  window.addEventListener("scroll", () => {
    closeMenu();
    hideFloatingTooltip();
  }, { passive: true });
  window.addEventListener("resize", () => {
    closeMenu();
    hideFloatingTooltip();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && searchDialog) {
      event.preventDefault();
      closeSearchDialog();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchDialog();
    }
  });
  const observer = new MutationObserver(() => initializeWorkspace());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  initializeWorkspace();
})();
